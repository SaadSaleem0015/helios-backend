from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "userkeys" DROP COLUMN "ghl_key";"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "userkeys" ADD "ghl_key" VARCHAR(500) NOT NULL;"""
