from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "user" ADD "fee_reminder_tries" INT NOT NULL DEFAULT 0;
        ALTER TABLE "user" ADD "fee_reminder_email" BOOL NOT NULL DEFAULT False;
        ALTER TABLE "user" ADD "last_fee_deducted" TIMESTAMPTZ;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "user" DROP COLUMN "fee_reminder_tries";
        ALTER TABLE "user" DROP COLUMN "fee_reminder_email";
        ALTER TABLE "user" DROP COLUMN "last_fee_deducted";"""
