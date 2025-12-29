from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "user" ADD "submit_for_approval" BOOL NOT NULL DEFAULT False;
        ALTER TABLE "user" ADD "is_active" BOOL NOT NULL DEFAULT True;
        ALTER TABLE "user" ADD "criteria_approved" BOOL NOT NULL DEFAULT False;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "user" DROP COLUMN "submit_for_approval";
        ALTER TABLE "user" DROP COLUMN "is_active";
        ALTER TABLE "user" DROP COLUMN "criteria_approved";"""
