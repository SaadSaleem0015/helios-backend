from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "assistant" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "vapi_assistant_id" VARCHAR(255),
    "name" VARCHAR(255) NOT NULL,
    "provider" VARCHAR(255) NOT NULL,
    "first_message" VARCHAR(255) NOT NULL,
    "model" VARCHAR(255) NOT NULL,
    "systemPrompt" TEXT NOT NULL,
    "knowledgeBase" JSONB,
    "leadsfile" JSONB,
    "temperature" DOUBLE PRECISION,
    "maxTokens" INT,
    "transcribe_provider" VARCHAR(255),
    "transcribe_language" VARCHAR(255),
    "transcribe_model" VARCHAR(255),
    "voice_provider" VARCHAR(255),
    "voice" VARCHAR(255),
    "forwardingPhoneNumber" VARCHAR(255),
    "endCallPhrases" JSONB,
    "attached_Number" VARCHAR(255),
    "vapi_phone_uuid" VARCHAR(255),
    "draft" BOOL DEFAULT False,
    "assistant_toggle" BOOL,
    "success_evalution" TEXT,
    "category" TEXT,
    "voice_model" TEXT,
    "languages" JSONB,
    "user_id" INT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE
);
        CREATE TABLE IF NOT EXISTS "purchasednumber" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "phone_number" VARCHAR(20) NOT NULL,
    "friendly_name" VARCHAR(255),
    "region" VARCHAR(255),
    "postal_code" VARCHAR(20),
    "iso_country" VARCHAR(10),
    "last_month_payment" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "attached_assistant" INT,
    "vapi_phone_uuid" VARCHAR(255),
    "user_id" INT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE
);
        CREATE TABLE IF NOT EXISTS "calllog" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "call_id" VARCHAR(1000),
    "vapi_id" VARCHAR(500),
    "lead_id" INT,
    "call_started_at" TIMESTAMPTZ,
    "customer_number" VARCHAR(100),
    "customer_name" VARCHAR(100),
    "cost" DECIMAL(10,2),
    "call_ended_at" TIMESTAMPTZ,
    "call_ended_reason" VARCHAR(100),
    "call_duration" DOUBLE PRECISION,
    "is_transferred" BOOL DEFAULT False,
    "status" VARCHAR(100),
    "criteria_satisfied" BOOL DEFAULT False,
    "user_id" INT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "assistant";
        DROP TABLE IF EXISTS "calllog";
        DROP TABLE IF EXISTS "purchasednumber";"""
