from tortoise.models import Model
from tortoise import fields
from enum import Enum


class SyncStatus(str, Enum):
    PENDING   = "pending"    # received, queued for processing
    SUCCESS   = "success"    # row written to sheet
    FAILED    = "failed"     # error after max retries
    RETRYING  = "retrying"   # manual retry in progress
    NO_CONFIG = "no_config"  # user hasn't set up sheet / mapping yet


class SheetSyncLog(Model):
    """
    One row per VAPI call end-of-call-report event.
    Provides full audit trail + retry capability.
    """

    id   = fields.IntField(primary_key=True)
    user = fields.ForeignKeyField(
        "models.User",
        on_delete=fields.CASCADE,
        related_name="sync_logs",
    )

    vapi_call_id   = fields.CharField(max_length=255)          # VAPI's call ID (for idempotency)
    status         = fields.CharEnumField(
        SyncStatus, max_length=20, default=SyncStatus.PENDING
    )

    # Raw transcript is stored so we can re-run extraction on retry
    raw_transcript = fields.TextField(null=True)

    # Metadata received directly from VAPI webhook (no LLM needed)
    call_ended_reason = fields.CharField(max_length=100, null=True)
    call_datetime     = fields.CharField(max_length=50, null=True)  # ISO string

    # LLM-extracted structured fields
    extracted_data = fields.JSONField(null=True)

    # Exact row list sent to Google Sheets API (useful for debugging)
    row_written = fields.JSONField(null=True)

    error_message = fields.TextField(null=True)
    retry_count   = fields.IntField(default=0)
    max_retries   = fields.IntField(default=3)
    synced_at     = fields.DatetimeField(null=True)

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table        = "sheet_sync_logs"
        ordering     = ["-created_at"]
        # Prevent duplicate processing of the same VAPI call per user
        unique_together = (("user", "vapi_call_id"),)