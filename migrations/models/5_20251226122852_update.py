from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "payment" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "amount_paid" DOUBLE PRECISION NOT NULL,
    "amount_received" DOUBLE PRECISION NOT NULL,
    "name_on_card" VARCHAR(255),
    "address" VARCHAR(255),
    "city" VARCHAR(100),
    "state" VARCHAR(100),
    "zip_code" VARCHAR(20),
    "last4" VARCHAR(4),
    "expiration_date" VARCHAR(7),
    "token" VARCHAR(255),
    "auto_replenishment" BOOL NOT NULL DEFAULT False,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" INT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE
);
        CREATE TABLE IF NOT EXISTS "paymentmethod" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "name_on_card" VARCHAR(255),
    "address" VARCHAR(255),
    "city" VARCHAR(100),
    "state" VARCHAR(100),
    "zip_code" VARCHAR(20),
    "last4" VARCHAR(4),
    "expiration_date" VARCHAR(7),
    "stripe_customer_id" TEXT,
    "payment_method_id" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "phone_number" VARCHAR(15),
    "email" VARCHAR(255),
    "is_primary" BOOL DEFAULT False,
    "user_id" INT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE
);
        CREATE TABLE IF NOT EXISTS "superadminsetting" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "max_call_duration" INT,
    "max_calls" INT,
    "transfer_rate" DOUBLE PRECISION,
    "monthly_fee" INT,
    "seconds_per_dollar" DOUBLE PRECISION,
    "call_frequency" INT NOT NULL DEFAULT 10,
    "call_period_minutes" INT NOT NULL DEFAULT 3,
    "max_call_limit_free_trial" INT NOT NULL DEFAULT 2000,
    "max_lead_limit_free_trial" INT NOT NULL DEFAULT 1000,
    "user_id" INT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "superadminsetting";
        DROP TABLE IF EXISTS "paymentmethod";
        DROP TABLE IF EXISTS "payment";"""
