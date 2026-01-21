from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "hubspotcrm" DROP COLUMN "client_id";
        ALTER TABLE "hubspotcrm" DROP COLUMN "client_secret";"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "hubspotcrm" ADD "client_id" VARCHAR(255) NOT NULL;
        ALTER TABLE "hubspotcrm" ADD "client_secret" TEXT NOT NULL;"""
