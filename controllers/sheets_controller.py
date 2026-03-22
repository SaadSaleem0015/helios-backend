"""
routers/sheets_router.py

Complete Google Sheets integration controller for multi-tenant SaaS.

Route map:
  OAuth & Connection
    GET  /sheets/auth-url                  → returns auth URL for frontend to redirect to
    GET  /sheets/callback                  → Google redirects here after consent (no JWT)
    GET  /sheets/status                    → connection + config health check
    DELETE /sheets/disconnect              → revoke tokens, clear all sheet config

  Sheet Configuration
    POST   /sheets/config                  → save sheet_id + tab_name + validate access
    GET    /sheets/config                  → get current sheet config
    POST   /sheets/config/validate         → re-validate sheet without saving

  Column Mapping
    POST   /sheets/mapping                 → upsert column mapping
    GET    /sheets/mapping                 → get current mapping
    DELETE /sheets/mapping                 → clear all column assignments

  Webhook (called by VAPI, not by the user)
    GET  /sheets/webhook-url               → return the user's unique VAPI webhook URL
    POST /sheets/webhook-secret/regenerate → rotate webhook secret (invalidates old URL)
    POST /sheets/webhook/{secret}          → VAPI post-call endpoint (no JWT auth)

  Sync Logs
    GET  /sheets/logs                      → paginated sync history
    GET  /sheets/logs/{log_id}             → single log detail
    POST /sheets/logs/{log_id}/retry       → manual retry of a failed sync

Required env vars (in addition to those in helpers):
    FRONTEND_BASE_URL   — e.g. https://app.yourdomain.com
    API_BASE_URL        — e.g. https://api.yourdomain.com
    ENCRYPTION_KEY      — Fernet key (also used for OAuth state encoding)
"""

import os
import secrets
from datetime import datetime, timezone
from typing import Annotated, Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, field_validator

from helpers.encryption import decrypt_token, encrypt_token, get_fernet
from helpers.google_oauth import (
    build_oauth_url,
    compute_expiry,
    exchange_code_for_tokens,
    get_google_user_info,
    revoke_token,
)
from helpers.jwt_token import get_current_user
from helpers.sheet_writer import (
    append_row_to_sheet,
    build_row_from_mapping,
    get_valid_access_token,
    validate_sheet_access,
)
from helpers.transcript_extractor import extract_fields_from_transcript
from models.sheetColumnMapping import SheetColumnMapping
from models.sheetSyncLog import SheetSyncLog, SyncStatus
from models.user import User
from models.user_keys import UserKeys

FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173")
API_BASE_URL      = os.getenv("API_BASE_URL","http://localhost:8000")

sheets_router = APIRouter(prefix="/sheets", tags=["Google Sheets"])


# ══════════════════════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _encode_oauth_state(user_id: int) -> str:
    """
    Stateless CSRF token for OAuth flow.
    Encodes user_id + UTC timestamp, encrypted with Fernet.
    Valid for 10 minutes.
    """
    payload = f"{user_id}:{int(datetime.now(timezone.utc).timestamp())}"
    return get_fernet().encrypt(payload.encode()).decode()


def _decode_oauth_state(state: str) -> int:
    """
    Decode and validate an OAuth state string.
    Returns user_id on success.
    Raises HTTP 400 if tampered, malformed, or older than 10 minutes.
    """
    try:
        payload   = get_fernet().decrypt(state.encode()).decode()
        user_id_s, ts_s = payload.split(":", 1)
        issued_at = datetime.fromtimestamp(int(ts_s), tz=timezone.utc)
        age_s     = (datetime.now(timezone.utc) - issued_at).total_seconds()
        if age_s > 600:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OAuth session expired. Please try connecting again.",
            )
        return int(user_id_s)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state. Please start the connection flow again.",
        )


async def _get_or_create_user_keys(user: User) -> UserKeys:
    """Return existing UserKeys row or create a bare one."""
    keys = await UserKeys.get_or_none(user=user)
    if not keys:
        keys = await UserKeys.create(user=user)
    return keys


def _is_google_connected(keys: UserKeys) -> bool:
    return bool(
        keys
        and keys.google_access_token
        and keys.google_refresh_token
    )


def _is_sheet_configured(keys: UserKeys) -> bool:
    return bool(keys and keys.sheet_id)


# ══════════════════════════════════════════════════════════════════════════════
# PYDANTIC SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class SheetConfigIn(BaseModel):
    sheet_id:       str = Field(..., min_length=10, description="Google Spreadsheet ID from the URL")
    sheet_tab_name: str = Field("Sheet1", min_length=1, max_length=255, description="Exact tab name (case-sensitive)")


class SheetConfigOut(BaseModel):
    sheet_id:       Optional[str]
    sheet_tab_name: Optional[str]
    google_email:   Optional[str]
    is_connected:   bool
    is_configured:  bool


class ColumnMappingIn(BaseModel):
    """
    Each field is the column letter the user wants to write to.
    null / omitted → skip that field.
    Accepted values: A–Z or multi-letter like AA, AB …
    """
    first_name_col:        Optional[str] = None
    last_name_col:         Optional[str] = None
    phone_number_col:      Optional[str] = None
    address_col:           Optional[str] = None
    city_col:              Optional[str] = None
    job_description_col:   Optional[str] = None
    call_ended_reason_col: Optional[str] = None
    call_datetime_col:     Optional[str] = None

    @field_validator(
        "first_name_col", "last_name_col", "phone_number_col",
        "address_col", "city_col", "job_description_col",
        "call_ended_reason_col", "call_datetime_col",
        mode="before",
    )
    @classmethod
    def validate_col_letter(cls, v):
        if v is None:
            return v
        v = str(v).strip().upper()
        if not v.isalpha():
            raise ValueError(f"Column must be letters only (e.g. A, B, AA). Got: '{v}'")
        return v


class ColumnMappingOut(ColumnMappingIn):
    pass


class SyncLogOut(BaseModel):
    id:               int
    vapi_call_id:     str
    status:           str
    call_ended_reason: Optional[str]
    call_datetime:    Optional[str]
    extracted_data:   Optional[dict]
    row_written:      Optional[list]
    error_message:    Optional[str]
    retry_count:      int
    synced_at:        Optional[datetime]
    created_at:       datetime


# ─── VAPI Webhook Payload Schema ──────────────────────────────────────────────

class VAPICustomer(BaseModel):
    number: Optional[str] = None

    class Config:
        extra = "allow"


class VAPICall(BaseModel):
    id:           Optional[str]     = None
    startedAt:    Optional[str]     = None
    endedAt:      Optional[str]     = None
    customer:     Optional[VAPICustomer] = None

    class Config:
        extra = "allow"


class VAPIMessage(BaseModel):
    type:         Optional[str]     = None
    endedReason:  Optional[str]     = None
    transcript:   Optional[str]     = None
    call:         Optional[VAPICall] = None

    class Config:
        extra = "allow"


class VAPIWebhookPayload(BaseModel):
    message: Optional[VAPIMessage] = None

    class Config:
        extra = "allow"


# ══════════════════════════════════════════════════════════════════════════════
# BACKGROUND TASK — called after VAPI webhook response is sent
# ══════════════════════════════════════════════════════════════════════════════

async def _process_call_sync(log_id: int, user_id: int) -> None:
    """
    Runs in the background after the VAPI webhook endpoint returns 200.

    Steps:
      1. Guard: verify config exists
      2. Extract transcript fields via LLM
      3. Build row using user's column mapping
      4. Get a valid (auto-refreshed) access token
      5. Append row to Google Sheet
      6. Update sync log with result
    """
    log = await SheetSyncLog.get_or_none(id=log_id)
    if not log:
        return

    # ── Step 1: Guard checks ─────────────────────────────────────────────────
    user_keys = await UserKeys.get_or_none(user_id=user_id)

    if not user_keys or not _is_google_connected(user_keys):
        log.status        = SyncStatus.NO_CONFIG
        log.error_message = "Google account not connected. Connect it in Settings → Integrations."
        await log.save()
        return

    if not _is_sheet_configured(user_keys):
        log.status        = SyncStatus.NO_CONFIG
        log.error_message = "No Google Sheet configured. Add Sheet ID in Settings → Integrations."
        await log.save()
        return

    mapping = await SheetColumnMapping.get_or_none(user_id=user_id)
    if not mapping:
        log.status        = SyncStatus.NO_CONFIG
        log.error_message = "Column mapping not configured. Set it up in Settings → Integrations."
        await log.save()
        return

    try:
        # ── Step 2: LLM extraction ───────────────────────────────────────────
        extracted = await extract_fields_from_transcript(log.raw_transcript or "")

        # Merge VAPI metadata (already on the log) into the extraction result
        extracted["call_ended_reason"] = log.call_ended_reason
        extracted["call_datetime"]     = log.call_datetime

        log.extracted_data = extracted
        await log.save()

        # ── Step 3: Build row ────────────────────────────────────────────────
        row = build_row_from_mapping(mapping, extracted)
        if not row:
            log.status        = SyncStatus.NO_CONFIG
            log.error_message = (
                "Column mapping has no columns assigned. "
                "Map at least one field in Settings → Integrations."
            )
            await log.save()
            return

        # ── Step 4: Get valid token ──────────────────────────────────────────
        access_token = await get_valid_access_token(user_keys)

        # ── Step 5: Write to sheet ───────────────────────────────────────────
        tab = user_keys.sheet_tab_name or "Sheet1"
        await append_row_to_sheet(access_token, user_keys.sheet_id, tab, row)

        # ── Step 6: Mark success ─────────────────────────────────────────────
        log.status        = SyncStatus.SUCCESS
        log.row_written   = row
        log.synced_at     = datetime.now(timezone.utc)
        log.error_message = None
        await log.save()

    except Exception as exc:
        log.retry_count  += 1
        log.status        = SyncStatus.FAILED
        log.error_message = str(exc)
        await log.save()


# ══════════════════════════════════════════════════════════════════════════════
# ROUTE 1 — OAuth: Get Auth URL
# ══════════════════════════════════════════════════════════════════════════════

@sheets_router.get("/auth-url")
async def get_auth_url(
    current: Annotated[User, Depends(get_current_user)],
):
    """
    Return the Google OAuth consent URL.
    Frontend should redirect the user's browser to this URL.
    """
    state    = _encode_oauth_state(current.id)
    auth_url = build_oauth_url(state)
    print(f"Generated OAuth URL for user {current.id}: {auth_url}")
    return {"auth_url": auth_url}


# ══════════════════════════════════════════════════════════════════════════════
# ROUTE 2 — OAuth: Callback (Browser Redirect — No JWT)
# ══════════════════════════════════════════════════════════════════════════════

@sheets_router.get("/callback")
async def google_oauth_callback(
    code:  Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
):
    """
    Google redirects the user's browser here after consent.
    No JWT auth — user identity comes from the encrypted `state` parameter.

    On success  → redirect to FRONTEND_BASE_URL/settings/integrations?sheet_connected=true
    On failure  → redirect to FRONTEND_BASE_URL/settings/integrations?sheet_error=<reason>
    """
    print(f"Received OAuth callback with code={code}, state={state}, error={error}")
    error_redirect = f"{FRONTEND_BASE_URL}/integrations/sheets?sheet_error="

    # User denied consent on Google's page
    if error:
        print(">>> FAILED: access_denied")   
        return RedirectResponse(url=f"{error_redirect}access_denied")

    if not code or not state:
        print(">>> FAILED: missing_params")
        return RedirectResponse(url=f"{error_redirect}missing_params")

    # Decode & validate state → get user_id
    try:
        user_id = _decode_oauth_state(state)
    except HTTPException:
        print(">>> FAILED: invalid_state") 
        return RedirectResponse(url=f"{error_redirect}invalid_state")

    # Fetch user
    user = await User.get_or_none(id=user_id)
    if not user or not user.is_active:
        print(">>> FAILED: user_not_found")                         
        return RedirectResponse(url=f"{error_redirect}user_not_found")

    # Exchange code for tokens
    try:
        token_data = await exchange_code_for_tokens(code)
    except httpx.HTTPStatusError:
        print(">>> FAILED: token_exchange_failed", e.response.text) 
        return RedirectResponse(url=f"{error_redirect}token_exchange_failed")

    access_token  = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in    = token_data.get("expires_in", 3600)
   
    if not access_token or not refresh_token:
        print(">>> FAILED: no_refresh_token")
        # refresh_token absent when user had previously authorized and we
        # didn't include prompt=consent — shouldn't happen with our URL config
        return RedirectResponse(url=f"{error_redirect}no_refresh_token")

    # Fetch Google account email
    try:
        user_info = await get_google_user_info(access_token)
        google_email = user_info.get("email", "")
    except Exception:
        google_email = ""

    # Persist encrypted tokens
    user_keys = await _get_or_create_user_keys(user)
    user_keys.google_access_token  = encrypt_token(access_token)
    user_keys.google_refresh_token = encrypt_token(refresh_token)
    user_keys.google_token_expiry   = compute_expiry(expires_in)
    user_keys.google_email          = google_email

    # Generate webhook secret if not already set
    if not user_keys.webhook_secret:
        user_keys.webhook_secret = secrets.token_urlsafe(32)

    await user_keys.save()
    print(">>> SUCCESS: saving tokens")
    return RedirectResponse(
        url=f"{FRONTEND_BASE_URL}/integrations/sheets?sheet_connected=true"
    )


# ══════════════════════════════════════════════════════════════════════════════
# ROUTE 3 — Status
# ══════════════════════════════════════════════════════════════════════════════

@sheets_router.get("/status")
async def get_connection_status(
    current: Annotated[User, Depends(get_current_user)],
):
    """
    Full health check for the Sheets integration.
    Frontend uses this to decide which setup steps to show.
    """
    keys = await UserKeys.filter(user=current).order_by('-id').first()
    print(f"Checking sheet status for user {current.id}: keys found: {bool(keys)}")
    mapping = await SheetColumnMapping.get_or_none(user=current)

    connected  = _is_google_connected(keys) if keys else False
    print("Google connected:", connected)
    configured = _is_sheet_configured(keys) if keys else False

    mapped_fields: list[str] = []
    if mapping:
        field_map = {
            "first_name":        mapping.first_name_col,
            "last_name":         mapping.last_name_col,
            "phone_number":      mapping.phone_number_col,
            "address":           mapping.address_col,
            "city":              mapping.city_col,
            "job_description":   mapping.job_description_col,
            "call_ended_reason": mapping.call_ended_reason_col,
            "call_datetime":     mapping.call_datetime_col,
        }
        mapped_fields = [f for f, col in field_map.items() if col]

    return {
        "is_google_connected":  connected,
        "google_email":         keys.google_email if keys else None,
        "is_sheet_configured":  configured,
        "sheet_id":             keys.sheet_id if keys else None,
        "sheet_tab_name":       keys.sheet_tab_name if keys else None,
        "is_mapping_configured": bool(mapped_fields),
        "mapped_fields":         mapped_fields,
        "has_webhook_secret":    bool(keys and keys.webhook_secret) if keys else False,
    }


# ══════════════════════════════════════════════════════════════════════════════
# ROUTE 4 — Disconnect
# ══════════════════════════════════════════════════════════════════════════════

@sheets_router.delete("/disconnect")
async def disconnect_google(
    current: Annotated[User, Depends(get_current_user)],
):
    """
    Revoke Google tokens and wipe all sheet config for this user.
    Column mapping is preserved so users don't have to redo it after reconnecting.
    """
    keys = await UserKeys.get_or_none(user=current)
    if not keys or not _is_google_connected(keys):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account is not connected.",
        )

    # Best-effort revoke at Google (token may already be expired)
    try:
        refresh_plain = decrypt_token(keys.google_refresh_token)
        await revoke_token(refresh_plain)
    except Exception:
        pass  # Revocation failure should not block disconnecting in our app

    keys.google_access_token  = None
    keys.google_refresh_token = None
    keys.google_token_expiry  = None
    keys.google_email         = None
    keys.sheet_id             = None
    keys.sheet_tab_name       = "Sheet1"
    await keys.save()

    return {"success" :True , "disconnected": True, "detail": "Google account disconnected successfully."}


# ══════════════════════════════════════════════════════════════════════════════
# ROUTE 5 — Sheet Config: Save + Validate
# ══════════════════════════════════════════════════════════════════════════════

@sheets_router.post("/config")
async def save_sheet_config(
    body:    SheetConfigIn,
    current: Annotated[User, Depends(get_current_user)],
):
    """
    Save the target spreadsheet ID and tab name.
    Validates access immediately — user gets instant feedback if something is wrong
    (wrong ID, no permission, tab doesn't exist).
    """
    keys = await UserKeys.get_or_none(user=current)

    if not keys or not _is_google_connected(keys):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connect your Google account first before configuring a sheet.",
        )

    access_token = await get_valid_access_token(keys)

    # validate_sheet_access raises descriptive HTTPException on any failure
    available_tabs = await validate_sheet_access(
        access_token, body.sheet_id, body.sheet_tab_name
    )

    keys.sheet_id       = body.sheet_id
    keys.sheet_tab_name = body.sheet_tab_name
    await keys.save()

    return {
        "sheet_id":        keys.sheet_id,
        "sheet_tab_name":  keys.sheet_tab_name,
        "available_tabs":  available_tabs,
        "message":         "Sheet configuration saved and verified successfully.",
    }


# ══════════════════════════════════════════════════════════════════════════════
# ROUTE 6 — Sheet Config: Get
# ══════════════════════════════════════════════════════════════════════════════

@sheets_router.get("/config")
async def get_sheet_config(
    current: Annotated[User, Depends(get_current_user)],
) -> SheetConfigOut:
    keys = await UserKeys.get_or_none(user=current)

    return SheetConfigOut(
        sheet_id       = keys.sheet_id       if keys else None,
        sheet_tab_name = keys.sheet_tab_name if keys else None,
        google_email   = keys.google_email   if keys else None,
        is_connected   = _is_google_connected(keys) if keys else False,
        is_configured  = _is_sheet_configured(keys) if keys else False,
    )


# ══════════════════════════════════════════════════════════════════════════════
# ROUTE 7 — Sheet Config: Re-validate (without saving)
# ══════════════════════════════════════════════════════════════════════════════

@sheets_router.post("/config/validate")
async def validate_sheet_config(
    body:    SheetConfigIn,
    current: Annotated[User, Depends(get_current_user)],
):
    """
    Test access to a sheet without persisting changes.
    Useful for a 'Test Connection' button in the UI.
    """
    keys = await UserKeys.get_or_none(user=current)

    if not keys or not _is_google_connected(keys):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connect your Google account first.",
        )

    access_token   = await get_valid_access_token(keys)
    available_tabs = await validate_sheet_access(
        access_token, body.sheet_id, body.sheet_tab_name
    )

    return {
        "valid":          True,
        "available_tabs": available_tabs,
        "message":        "Sheet and tab are accessible.",
    }


# ══════════════════════════════════════════════════════════════════════════════
# ROUTE 8 — Column Mapping: Upsert
# ══════════════════════════════════════════════════════════════════════════════

@sheets_router.post("/mapping")
async def save_column_mapping(
    body:    ColumnMappingIn,
    current: Annotated[User, Depends(get_current_user)],
):
    """
    Create or fully replace the user's column mapping.

    Duplicate column detection: two fields cannot share the same column letter
    — that would silently overwrite data in the sheet.
    """
    # ── Duplicate column check ────────────────────────────────────────────────
    col_assignments: dict[str, str] = {}  # col_letter → field_name
    for field, col in body.model_dump().items():
        if col is None:
            continue
        col_upper = col.upper()
        if col_upper in col_assignments:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Column '{col_upper}' is assigned to both "
                    f"'{col_assignments[col_upper]}' and '{field}'. "
                    f"Each field must map to a unique column."
                ),
            )
        col_assignments[col_upper] = field

    # ── Upsert ────────────────────────────────────────────────────────────────
    mapping = await SheetColumnMapping.get_or_none(user=current)
    data    = body.model_dump()

    if mapping:
        for field, value in data.items():
            setattr(mapping, field, value)
        await mapping.save()
    else:
        mapping = await SheetColumnMapping.create(user=current, **data)

    return {
        "mapping": ColumnMappingOut(**data),
        "message": "Column mapping saved successfully.",
    }


# ══════════════════════════════════════════════════════════════════════════════
# ROUTE 9 — Column Mapping: Get
# ══════════════════════════════════════════════════════════════════════════════

@sheets_router.get("/mapping")
async def get_column_mapping(
    current: Annotated[User, Depends(get_current_user)],
):
    mapping = await SheetColumnMapping.get_or_none(user=current)
    if not mapping:
        # Return a blank mapping so frontend can show the config form
        return {"mapping": None, "is_configured": False}

    return {
        "mapping": ColumnMappingOut(
            first_name_col        = mapping.first_name_col,
            last_name_col         = mapping.last_name_col,
            phone_number_col      = mapping.phone_number_col,
            address_col           = mapping.address_col,
            city_col              = mapping.city_col,
            job_description_col   = mapping.job_description_col,
            call_ended_reason_col = mapping.call_ended_reason_col,
            call_datetime_col     = mapping.call_datetime_col,
        ),
        "is_configured": True,
    }


# ══════════════════════════════════════════════════════════════════════════════
# ROUTE 10 — Column Mapping: Clear
# ══════════════════════════════════════════════════════════════════════════════

@sheets_router.delete("/mapping")
async def clear_column_mapping(
    current: Annotated[User, Depends(get_current_user)],
):
    """Set all column assignments to null (does not delete the row)."""
    mapping = await SheetColumnMapping.get_or_none(user=current)
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No column mapping exists to clear.",
        )

    null_fields = {
        "first_name_col":        None,
        "last_name_col":         None,
        "phone_number_col":      None,
        "address_col":           None,
        "city_col":              None,
        "job_description_col":   None,
        "call_ended_reason_col": None,
        "call_datetime_col":     None,
    }
    for field, val in null_fields.items():
        setattr(mapping, field, val)
    await mapping.save()

    return {"cleared": True, "message": "All column assignments cleared."}


# ══════════════════════════════════════════════════════════════════════════════
# ROUTE 11 — Webhook URL
# ══════════════════════════════════════════════════════════════════════════════

@sheets_router.get("/webhook-url")
async def get_webhook_url(
    current: Annotated[User, Depends(get_current_user)],
):
    """
    Return the unique VAPI webhook URL for this user.
    The user pastes this into VAPI → Assistant → Server URL.
    """
    keys = await _get_or_create_user_keys(current)

    if not keys.webhook_secret:
        # Auto-generate if missing (e.g. user created account before this feature)
        keys.webhook_secret = secrets.token_urlsafe(32)
        await keys.save()

    webhook_url = f"{API_BASE_URL}/sheets/webhook/{keys.webhook_secret}"
    return {
        "webhook_url":    webhook_url,
        "webhook_secret": keys.webhook_secret,
        "instructions":   (
            "Paste this URL into your VAPI Assistant's 'Server URL' field. "
            "VAPI will POST call data here when each call ends."
        ),
    }


# ══════════════════════════════════════════════════════════════════════════════
# ROUTE 12 — Webhook Secret: Rotate
# ══════════════════════════════════════════════════════════════════════════════

@sheets_router.post("/webhook-secret/regenerate")
async def regenerate_webhook_secret(
    current: Annotated[User, Depends(get_current_user)],
):
    """
    Rotate the webhook secret.  Old VAPI URL stops working immediately.
    User must update their VAPI assistant with the new URL.
    """
    keys = await _get_or_create_user_keys(current)
    keys.webhook_secret = secrets.token_urlsafe(32)
    await keys.save()

    new_url = f"{API_BASE_URL}/sheets/webhook/{keys.webhook_secret}"
    return {
        "webhook_url":    new_url,
        "webhook_secret": keys.webhook_secret,
        "warning": (
            "Your old webhook URL is now invalid. "
            "Update VAPI with the new URL immediately to avoid missed syncs."
        ),
    }


# ══════════════════════════════════════════════════════════════════════════════
# ROUTE 13 — VAPI Webhook (No JWT — identified by secret)
# ══════════════════════════════════════════════════════════════════════════════

@sheets_router.post("/webhook/{secret}", status_code=status.HTTP_200_OK)
async def vapi_post_call_webhook(
    secret:           str,
    payload:          VAPIWebhookPayload,
    background_tasks: BackgroundTasks,
):
    """
    VAPI calls this endpoint when a call ends (end-of-call-report event).

    Security:  URL secret is 256-bit random token — effectively a bearer token.
    Idempotent: duplicate VAPI retries for the same call_id are silently ignored.
    Fast:      returns 200 immediately; all heavy work runs in BackgroundTasks.

    VAPI requires a fast response — do not do any heavy work synchronously here.
    """
    # ── 1. Identify the user from the secret ─────────────────────────────────
    keys = await UserKeys.get_or_none(webhook_secret=secret)
    if not keys:
        # Return 200 even for unknown secrets — don't leak information
        # and don't cause VAPI to retry indefinitely
        return {"received": True}

    await keys.fetch_related("user")
    user = keys.user

    # ── 2. Guard: only process end-of-call-report events ─────────────────────
    msg = payload.message
    if not msg or msg.type != "end-of-call-report":
        return {"received": True, "note": "Event type ignored."}

    call         = msg.call or VAPICall()
    vapi_call_id = call.id

    if not vapi_call_id:
        return {"received": True, "note": "No call ID in payload."}

    # ── 3. Idempotency — skip if already processed ────────────────────────────
    existing_log = await SheetSyncLog.get_or_none(
        user=user,
        vapi_call_id=vapi_call_id,
    )
    if existing_log:
        return {"received": True, "note": "Already processed."}

    # ── 4. Extract VAPI metadata (no LLM needed for these fields) ────────────
    call_ended_reason = msg.endedReason
    call_datetime     = call.endedAt or call.startedAt  # prefer endedAt

    # ── 5. Create sync log (PENDING) ─────────────────────────────────────────
    log = await SheetSyncLog.create(
        user              = user,
        vapi_call_id      = vapi_call_id,
        status            = SyncStatus.PENDING,
        raw_transcript    = msg.transcript,
        call_ended_reason = call_ended_reason,
        call_datetime     = call_datetime,
    )

    # ── 6. Queue the heavy work ───────────────────────────────────────────────
    background_tasks.add_task(_process_call_sync, log.id, user.id)

    return {"received": True, "log_id": log.id}


# ══════════════════════════════════════════════════════════════════════════════
# ROUTE 14 — Sync Logs: List (Paginated)
# ══════════════════════════════════════════════════════════════════════════════

@sheets_router.get("/logs")
async def list_sync_logs(
    current: Annotated[User, Depends(get_current_user)],
    page:    int            = Query(1,   ge=1),
    limit:   int            = Query(20,  ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    """
    Paginated sync history for the current user.
    Optionally filter by status: pending | success | failed | retrying | no_config
    """
    qs = SheetSyncLog.filter(user=current)

    if status_filter:
        try:
            qs = qs.filter(status=SyncStatus(status_filter))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status filter '{status_filter}'. "
                       f"Valid values: {[s.value for s in SyncStatus]}",
            )

    total  = await qs.count()
    offset = (page - 1) * limit
    logs   = await qs.offset(offset).limit(limit)

    return {
        "total":    total,
        "page":     page,
        "limit":    limit,
        "pages":    (total + limit - 1) // limit,
        "results":  [
            SyncLogOut(
                id               = log.id,
                vapi_call_id     = log.vapi_call_id,
                status           = log.status,
                call_ended_reason = log.call_ended_reason,
                call_datetime    = log.call_datetime,
                extracted_data   = log.extracted_data,
                row_written      = log.row_written,
                error_message    = log.error_message,
                retry_count      = log.retry_count,
                synced_at        = log.synced_at,
                created_at       = log.created_at,
            )
            for log in logs
        ],
    }


# ══════════════════════════════════════════════════════════════════════════════
# ROUTE 15 — Sync Logs: Single
# ══════════════════════════════════════════════════════════════════════════════

@sheets_router.get("/logs/{log_id}")
async def get_sync_log(
    log_id:  int,
    current: Annotated[User, Depends(get_current_user)],
):
    log = await SheetSyncLog.get_or_none(id=log_id, user=current)
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sync log not found.",
        )

    return SyncLogOut(
        id               = log.id,
        vapi_call_id     = log.vapi_call_id,
        status           = log.status,
        call_ended_reason = log.call_ended_reason,
        call_datetime    = log.call_datetime,
        extracted_data   = log.extracted_data,
        row_written      = log.row_written,
        error_message    = log.error_message,
        retry_count      = log.retry_count,
        synced_at        = log.synced_at,
        created_at       = log.created_at,
    )


# ══════════════════════════════════════════════════════════════════════════════
# ROUTE 16 — Sync Logs: Manual Retry
# ══════════════════════════════════════════════════════════════════════════════

@sheets_router.post("/logs/{log_id}/retry")
async def retry_sync_log(
    log_id:           int,
    current:          Annotated[User, Depends(get_current_user)],
    background_tasks: BackgroundTasks,
):
    """
    Manually retry a failed or no_config sync.
    Only allowed for logs in FAILED or NO_CONFIG status.
    Retry count is not incremented by manual retries (only by automatic failures).
    """
    log = await SheetSyncLog.get_or_none(id=log_id, user=current)
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sync log not found.",
        )

    if log.status not in (SyncStatus.FAILED, SyncStatus.NO_CONFIG):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot retry a log with status '{log.status}'. "
                   f"Only 'failed' and 'no_config' logs can be retried.",
        )

    # Reset to RETRYING so it's clear in the UI something is happening
    log.status        = SyncStatus.RETRYING
    log.error_message = None
    await log.save()

    background_tasks.add_task(_process_call_sync, log.id, current.id)

    return {
        "retrying": True,
        "log_id":   log_id,
        "message":  "Retry queued. Check the log status in a few seconds.",
    }