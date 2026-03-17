from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "sheet_column_mappings" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "first_name_col" VARCHAR(5),
    "last_name_col" VARCHAR(5),
    "phone_number_col" VARCHAR(5),
    "address_col" VARCHAR(5),
    "city_col" VARCHAR(5),
    "job_description_col" VARCHAR(5),
    "call_ended_reason_col" VARCHAR(5),
    "call_datetime_col" VARCHAR(5),
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" INT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "sheet_column_mappings" IS 'Stores which column letter (A, B, C …) each system field maps to';
        CREATE TABLE IF NOT EXISTS "sheet_sync_logs" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "vapi_call_id" VARCHAR(255) NOT NULL,
    "status" VARCHAR(20) NOT NULL DEFAULT 'pending',
    "raw_transcript" TEXT,
    "call_ended_reason" VARCHAR(100),
    "call_datetime" VARCHAR(50),
    "extracted_data" JSONB,
    "row_written" JSONB,
    "error_message" TEXT,
    "retry_count" INT NOT NULL DEFAULT 0,
    "max_retries" INT NOT NULL DEFAULT 3,
    "synced_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" INT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_sheet_sync__user_id_aba72e" UNIQUE ("user_id", "vapi_call_id")
);
COMMENT ON COLUMN "sheet_sync_logs"."status" IS 'PENDING: pending\nSUCCESS: success\nFAILED: failed\nRETRYING: retrying\nNO_CONFIG: no_config';
COMMENT ON TABLE "sheet_sync_logs" IS 'One row per VAPI call end-of-call-report event.';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "sheet_sync_logs";
        DROP TABLE IF EXISTS "sheet_column_mappings";"""
