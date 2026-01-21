from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "closecrm" ADD "organization_id" VARCHAR(100);
        ALTER TABLE "closecrm" ADD "refresh_token" TEXT;
        ALTER TABLE "closecrm" RENAME COLUMN "api_key" TO "client_secret";
        ALTER TABLE "closecrm" ADD "expires_at" TIMESTAMPTZ;
        ALTER TABLE "closecrm" ADD "access_token" TEXT;
        ALTER TABLE "closecrm" ADD "client_id" VARCHAR(255) NOT NULL;
        ALTER TABLE "closecrm" ADD "close_user_id" VARCHAR(100);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "closecrm" RENAME COLUMN "client_secret" TO "api_key";
        ALTER TABLE "closecrm" DROP COLUMN "organization_id";
        ALTER TABLE "closecrm" DROP COLUMN "refresh_token";
        ALTER TABLE "closecrm" DROP COLUMN "expires_at";
        ALTER TABLE "closecrm" DROP COLUMN "access_token";
        ALTER TABLE "closecrm" DROP COLUMN "client_id";
        ALTER TABLE "closecrm" DROP COLUMN "close_user_id";"""
