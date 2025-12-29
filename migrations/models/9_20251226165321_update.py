from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "schedule" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "title" VARCHAR(255) NOT NULL,
    "timezone" VARCHAR(255) NOT NULL,
    "complete_schedule" JSONB NOT NULL,
    "user_id" INT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE
);
        CREATE TABLE IF NOT EXISTS "scheduletime" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "from_time" TIMETZ NOT NULL,
    "to_time" TIMETZ NOT NULL,
    "day" VARCHAR(255) NOT NULL,
    "schedule_id" INT NOT NULL REFERENCES "schedule" ("id") ON DELETE CASCADE
);
        CREATE TABLE IF NOT EXISTS "schedulecall" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "vapi_assistant_id" VARCHAR(255),
    "title" VARCHAR(50),
    "date" JSONB NOT NULL,
    "file_id" JSONB NOT NULL,
    "leads" JSONB NOT NULL,
    "status" VARCHAR(50) NOT NULL DEFAULT 'pending',
    "timeZone" VARCHAR(20),
    "call_id" JSONB NOT NULL,
    "schedule" JSONB NOT NULL,
    "user_id" INT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE
);
        CREATE TABLE IF NOT EXISTS "leadstatus" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "lead_id" INT NOT NULL,
    "status" VARCHAR(20) NOT NULL DEFAULT 'Pending',
    "ended_reason" TEXT,
    "customer_name" TEXT,
    "schedule_call_id" INT NOT NULL REFERENCES "schedulecall" ("id") ON DELETE CASCADE
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "scheduletime";
        DROP TABLE IF EXISTS "schedulecall";
        DROP TABLE IF EXISTS "schedule";
        DROP TABLE IF EXISTS "leadstatus";"""
