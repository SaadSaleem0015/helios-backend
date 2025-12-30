from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "zohocrm" ADD "user_id" INT NOT NULL;
        ALTER TABLE "zohocrm" ADD CONSTRAINT "fk_zohocrm_user_b16d1b71" FOREIGN KEY ("user_id") REFERENCES "user" ("id") ON DELETE CASCADE;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "zohocrm" DROP CONSTRAINT IF EXISTS "fk_zohocrm_user_b16d1b71";
        ALTER TABLE "zohocrm" DROP COLUMN "user_id";"""
