from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "defaultsettings" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "max_call_duration" INT DEFAULT 100,
    "max_calls" INT DEFAULT 50,
    "transfer_rate" DOUBLE PRECISION DEFAULT 2,
    "monthly_fee" INT DEFAULT 100,
    "phone_number_price" INT DEFAULT 5,
    "seconds_per_dollar" DOUBLE PRECISION DEFAULT 60,
    "call_frequency" INT NOT NULL DEFAULT 10,
    "call_period_minutes" INT NOT NULL DEFAULT 3,
    "max_call_limit_free_trial" INT NOT NULL DEFAULT 2000,
    "max_lead_limit_free_trial" INT NOT NULL DEFAULT 3000
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "defaultsettings";"""
