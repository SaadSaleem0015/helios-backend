from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "document" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "file_name" VARCHAR(255) NOT NULL,
    "vapi_file_id" VARCHAR(255),
    "user_id" INT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "document";"""
