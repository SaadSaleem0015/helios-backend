"""
helpers/google_oauth.py

Handles all Google OAuth 2.0 communication:
  - Building the consent screen URL
  - Exchanging auth code for tokens
  - Refreshing expired access tokens
  - Fetching the connected Google account's email

Required env vars:
    GOOGLE_CLIENT_ID       — from Google Cloud Console
    GOOGLE_CLIENT_SECRET   — from Google Cloud Console
    GOOGLE_REDIRECT_URI    — e.g. https://api.yourdomain.com/sheets/callback
"""

import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx

GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI  = os.getenv("GOOGLE_REDIRECT_URI")

# Scopes: spreadsheets read/write + basic profile to show which account is connected
SCOPES = " ".join([
    "https://www.googleapis.com/auth/spreadsheets",
    "openid",
    "email",
    "profile",
])


# ─── URL Builder ──────────────────────────────────────────────────────────────

def build_oauth_url(state: str) -> str:
    """
    Build the Google OAuth consent URL.
    `state` is an encrypted, tamper-proof string containing user_id + timestamp.

    `access_type=offline` + `prompt=consent` ensures we always receive a
    refresh_token even if the user has previously authorized.
    """
    params = {
        "client_id":     GOOGLE_CLIENT_ID,
        "redirect_uri":  GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope":         SCOPES,
        "access_type":   "offline",
        "prompt":        "consent",
        "state":         state,
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


# ─── Token Exchange ───────────────────────────────────────────────────────────

async def exchange_code_for_tokens(code: str) -> dict:
    """
    Exchange the one-time authorization code (from the callback) for
    access_token + refresh_token.

    Returns the full token response dict from Google.
    Raises httpx.HTTPStatusError on failure.
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code":          code,
                "client_id":     GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri":  GOOGLE_REDIRECT_URI,
                "grant_type":    "authorization_code",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def refresh_access_token(refresh_token_plain: str) -> dict:
    """
    Use the refresh token to obtain a new access token.

    Returns dict with at minimum: access_token, expires_in.
    Raises httpx.HTTPStatusError if the refresh token has been revoked.
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "refresh_token": refresh_token_plain,
                "client_id":     GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "grant_type":    "refresh_token",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def revoke_token(token_plain: str) -> None:
    """
    Revoke an access or refresh token at Google.
    Best-effort — we do not raise on failure (token may already be expired).
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(
            "https://oauth2.googleapis.com/revoke",
            params={"token": token_plain},
        )


async def get_google_user_info(access_token: str) -> dict:
    """
    Fetch basic profile info (email, name) for the connected Google account.
    Used to display 'Connected as: user@gmail.com' in the UI.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()


# ─── Utility ─────────────────────────────────────────────────────────────────

def compute_expiry(expires_in: int) -> datetime:
    """Convert `expires_in` seconds (from Google's response) to an absolute UTC datetime."""
    return datetime.now(timezone.utc) + timedelta(seconds=expires_in)