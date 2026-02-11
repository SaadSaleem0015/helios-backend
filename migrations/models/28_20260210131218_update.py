from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "supportticket" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "ticket_number" VARCHAR(20) NOT NULL UNIQUE,
    "subject" VARCHAR(255) NOT NULL,
    "description" TEXT NOT NULL,
    "priority" VARCHAR(6) NOT NULL DEFAULT 'medium',
    "status" VARCHAR(11) NOT NULL DEFAULT 'open',
    "admin_notes" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "resolved_by_id" INT REFERENCES "user" ("id") ON DELETE CASCADE,
    "user_id" INT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "supportticket"."priority" IS 'LOW: low\nMEDIUM: medium\nHIGH: high';
COMMENT ON COLUMN "supportticket"."status" IS 'OPEN: open\nIN_PROGRESS: in_progress\nRESOLVED: resolved\nCLOSED: closed';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "supportticket";"""
