from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "userkeys" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "ghl_key" VARCHAR(500) NOT NULL,
    "google_access_token" TEXT,
    "google_refresh_token" TEXT,
    "google_token_expiry" TIMESTAMPTZ,
    "google_email" VARCHAR(255),
    "sheet_id" VARCHAR(500),
    "sheet_tab_name" VARCHAR(255) DEFAULT 'Sheet1',
    "webhook_secret" VARCHAR(64) UNIQUE,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" INT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "userkeys";"""
