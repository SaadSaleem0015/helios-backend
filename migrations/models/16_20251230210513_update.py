from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "file" ADD "type" VARCHAR(8) UNIQUE;
        CREATE UNIQUE INDEX IF NOT EXISTS "uid_file_type_8005ff" ON "file" ("type");"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP INDEX IF EXISTS "uid_file_type_8005ff";
        ALTER TABLE "file" DROP COLUMN "type";"""
