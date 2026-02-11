from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "calcomintegration" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "api_key" VARCHAR(255) NOT NULL,
    "event_type_id" INT NOT NULL,
    "slug" VARCHAR(100) NOT NULL,
    "time_zone" VARCHAR(100) NOT NULL,
    "event_name" VARCHAR(255),
    "length_minutes" INT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "is_active" BOOL NOT NULL DEFAULT True,
    "user_id" INT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "calcomintegration" IS 'Stores Cal.com API key + selected event type per user.';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "calcomintegration";"""
