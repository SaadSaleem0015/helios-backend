"""
helpers/transcript_extractor.py

Uses Claude (Anthropic API) to extract structured fields from a raw call
transcript.  Returns a dict with exactly 6 keys — all nullable.

Why Claude and not a regex approach?
  • Transcripts are messy, conversational, and unpredictable.
  • LLMs handle name variations, rephrasing, and partial info gracefully.
  • Structured prompting with explicit null semantics avoids hallucination.

Required env var:
    ANTHROPIC_API_KEY
"""

import json
import os
from typing import Optional

import httpx

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# ─── Prompts ─────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are a data-extraction assistant specialising in sales and service call transcripts. "
    "Extract only what is explicitly stated. Never guess or infer. "
    "Respond with a single valid JSON object — no markdown, no explanation, no extra keys."
)

_USER_PROMPT = """\
Extract the following fields from the call transcript below.
Return null for any field that is not clearly mentioned.

Fields:
  first_name       — Lead or caller's first name
  last_name        — Lead or caller's last name
  phone_number     — Phone number (exactly as spoken or stated)
  address          — Street address (house number + street name)
  city             — City name
  job_description  — Job title, occupation, or role

Required JSON structure (all keys must be present):
{{
  "first_name": "string | null",
  "last_name": "string | null",
  "phone_number": "string | null",
  "address": "string | null",
  "city": "string | null",
  "job_description": "string | null"
}}

TRANSCRIPT:
{transcript}"""

# Returned when transcript is empty or LLM fails — all nulls
_NULL_RESULT: dict = {
    "first_name":      None,
    "last_name":       None,
    "phone_number":    None,
    "address":         None,
    "city":            None,
    "job_description": None,
}

_EXPECTED_KEYS = set(_NULL_RESULT.keys())


# ─── Main Function ────────────────────────────────────────────────────────────

async def extract_fields_from_transcript(transcript: str) -> dict:
    """
    Extract structured fields from a call transcript using Claude.

    - Returns all nulls for empty/whitespace transcripts (no API call made).
    - Falls back to all nulls if JSON parsing fails (never raises).
    - Sanitises the output to ensure only expected keys are returned.
    """
    if not transcript or not transcript.strip():
        return _NULL_RESULT.copy()

    prompt = _USER_PROMPT.format(transcript=transcript.strip())

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key":         ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type":      "application/json",
                },
                json={
                    "model":      "claude-sonnet-4-20250514",
                    "max_tokens": 512,
                    "system":     _SYSTEM_PROMPT,
                    "messages":   [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            raw_text: str = resp.json()["content"][0]["text"].strip()

    except Exception:
        # LLM call failed — return nulls so the rest of the pipeline continues
        return _NULL_RESULT.copy()

    # ── Strip accidental markdown fences ─────────────────────────────────────
    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        # Remove first line (```json or ```) and last line (```)
        raw_text = "\n".join(lines[1:-1] if len(lines) > 2 else lines[1:])

    # ── Parse JSON ────────────────────────────────────────────────────────────
    try:
        extracted: dict = json.loads(raw_text.strip())
    except json.JSONDecodeError:
        return _NULL_RESULT.copy()

    # ── Sanitise output ───────────────────────────────────────────────────────
    # Keep only expected keys; normalise non-null values to stripped strings;
    # treat empty strings as null.
    result: dict = {}
    for key in _EXPECTED_KEYS:
        val = extracted.get(key)
        if val is not None and isinstance(val, str) and val.strip():
            result[key] = val.strip()
        else:
            result[key] = None

    return result