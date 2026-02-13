from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "user" ADD "low_balance_email_sent" BOOL NOT NULL DEFAULT False;
        ALTER TABLE "payment" ADD "description" VARCHAR(255);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "user" DROP COLUMN "low_balance_email_sent";
        ALTER TABLE "payment" DROP COLUMN "description";"""
