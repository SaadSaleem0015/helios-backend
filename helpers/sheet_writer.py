"""
helpers/sheet_writer.py

Three responsibilities:
  1. Token lifecycle  — get a valid (auto-refreshed) access token
  2. Column mapping   — convert {field: col_letter} + data into a row list
  3. Sheets API       — append rows, validate sheet access
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import HTTPException, status

from helpers.encryption import encrypt_token, decrypt_token
from helpers.google_oauth import refresh_access_token, compute_expiry

SHEETS_BASE = "https://sheets.googleapis.com/v4/spreadsheets"


# ─── 1. Token Lifecycle ───────────────────────────────────────────────────────

async def get_valid_access_token(user_keys) -> str:
    """
    Returns a usable access token for the given UserKeys row.

    If the token is missing, expired, or expires within 5 minutes,
    it transparently refreshes using the refresh token and persists
    the new access token + expiry back to the DB.

    Raises HTTP 401 if Google account is not connected at all.
    """
    now = datetime.now(timezone.utc)

    # Normalise DB datetime to timezone-aware (Tortoise can return naive datetimes)
    expiry = user_keys.google_token_expiry
    if expiry is not None and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)

    needs_refresh = expiry is None or expiry <= now + timedelta(minutes=5)

    if needs_refresh:
        if not user_keys.google_refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google account is not connected. Please connect it in Settings.",
            )
        refresh_plain = decrypt_token(user_keys.google_refresh_token)
        try:
            token_data = await refresh_access_token(refresh_plain)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (400, 401):
                # Refresh token revoked by user in Google account settings
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Google authorization was revoked. Please reconnect your account.",
                )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to refresh Google token. Please try again later.",
            )

        user_keys.google_access_token = encrypt_token(token_data["access_token"])
        user_keys.google_token_expiry  = compute_expiry(token_data.get("expires_in", 3600))
        await user_keys.save()

        return token_data["access_token"]

    return decrypt_token(user_keys.google_access_token)


# ─── 2. Column Mapping ────────────────────────────────────────────────────────

def col_letter_to_index(col: str) -> int:
    """
    Convert a column letter to a 0-based integer index.
    A→0, B→1, Z→25, AA→26, AB→27 …

    Raises ValueError for invalid input.
    """
    col = col.upper().strip()
    if not col or not col.isalpha():
        raise ValueError(f"Invalid column letter: '{col}'")
    result = 0
    for char in col:
        result = result * 26 + (ord(char) - ord("A") + 1)
    return result - 1


def build_row_from_mapping(mapping_obj, data: dict) -> list:
    """
    Produce a flat list suitable for Google Sheets API valueRange.values[0].

    mapping_obj : SheetColumnMapping instance
    data        : dict with keys matching the system field names below

    Rules:
      • Fields with null column → skipped entirely
      • Gaps between mapped columns are filled with ""
      • None values in data → written as ""
      • Returns [] if no column is mapped (caller should abort write)

    Example:
        mapping  : first_name→A, last_name→B, phone_number→D
        data     : {first_name:"John", last_name:"Doe", phone_number:"555"}
        output   : ["John", "Doe", "", "555"]
    """
    field_to_col: dict[str, Optional[str]] = {
        "first_name":        mapping_obj.first_name_col,
        "last_name":         mapping_obj.last_name_col,
        "phone_number":      mapping_obj.phone_number_col,
        "address":           mapping_obj.address_col,
        "city":              mapping_obj.city_col,
        "job_description":   mapping_obj.job_description_col,
        "call_ended_reason": mapping_obj.call_ended_reason_col,
        "call_datetime":     mapping_obj.call_datetime_col,
    }

    # Keep only fields that have a non-empty column letter assigned
    active: dict[str, str] = {
        field: col.upper().strip()
        for field, col in field_to_col.items()
        if col and col.strip()
    }

    if not active:
        return []

    # Compute the 0-based index for every active column
    indices: dict[str, int] = {
        field: col_letter_to_index(col)
        for field, col in active.items()
    }

    max_index = max(indices.values())
    row: list = [""] * (max_index + 1)

    for field, idx in indices.items():
        value = data.get(field)
        row[idx] = str(value).strip() if value is not None and str(value).strip() else ""

    return row


# ─── 3. Sheets API ────────────────────────────────────────────────────────────

async def validate_sheet_access(
    access_token: str,
    sheet_id: str,
    tab_name: str,
) -> list[str]:
    """
    Confirm the access token can reach the sheet and the tab exists.

    Returns list of all available tab names on success.
    Raises descriptive HTTPException on any failure.
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{SHEETS_BASE}/{sheet_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if resp.status_code == 404:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Google Sheet not found. Verify the Sheet ID is correct.",
        )
    if resp.status_code == 403:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Access denied to this Sheet. Make sure the connected Google "
                "account has at least Editor access to the spreadsheet."
            ),
        )
    if not resp.is_success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Google Sheets API returned {resp.status_code}. Please try again.",
        )

    meta = resp.json()
    available_tabs: list[str] = [
        sheet["properties"]["title"]
        for sheet in meta.get("sheets", [])
    ]

    if tab_name not in available_tabs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Tab '{tab_name}' not found in the sheet. "
                f"Available tabs: {', '.join(available_tabs)}"
            ),
        )

    return available_tabs


async def append_row_to_sheet(
    access_token: str,
    sheet_id: str,
    tab_name: str,
    row_data: list,
) -> dict:
    """
    Append row_data as a new row at the end of the given tab.

    Uses USER_ENTERED so dates/numbers are interpreted by Sheets normally.
    Raises httpx.HTTPStatusError on Google API failure.
    """
    # Single-quote the tab name to handle tabs with spaces or special chars
    range_notation = f"'{tab_name}'!A1"

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            f"{SHEETS_BASE}/{sheet_id}/values/{range_notation}:append",
            headers={"Authorization": f"Bearer {access_token}"},
            params={
                "valueInputOption": "USER_ENTERED",
                "insertDataOption": "INSERT_ROWS",
            },
            json={"values": [row_data]},
        )
        resp.raise_for_status()
        print(f"Successfully appended row to sheet {sheet_id}, tab {tab_name}: {row_data}")
        return resp.json()