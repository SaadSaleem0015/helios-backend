from dotenv import load_dotenv
load_dotenv()
from tortoise import Tortoise
from contextlib import asynccontextmanager
import os


db_url = os.getenv("DATABASE_URI")
if not db_url:
    raise ValueError("DATABASE_URI environment variable is not set.")


TORTOISE_CONFIG = {

    'connections': {
        'default': db_url
    },
    "apps": {
        "models": {
            "models": [
                "models.user",
                "models.code",
                "models.file",
                "models.lead",
                "models.assistant",
                "models.purchased_number",
                "models.call_log",
                "models.document",
                "models.payment",
                "models.paymentMethod",
                "models.super_admin_setting",
                "models.defaultSettings",
                "models.timeLimit",
                "models.spent",
                "models.schedule",
                "models.schedule_time",
                "models.schedule_call",
                "models.lead_status",
                "models.termsandconditions",
                "models.zoho_crm",
                "models.close_crm",
                "models.hubspot_crm",
                "models.twilio_credentials",
                "models.dnc",

                "models.auto_replenishment",
                "aerich.models"
            ]
        }
    }
    }


@asynccontextmanager
async def lifespan(_):
    await Tortoise.init(config=TORTOISE_CONFIG)
    try:
        yield
    finally:
        await Tortoise.close_connections()

async def init_tortoise():
    await Tortoise.init(config=TORTOISE_CONFIG)
    await Tortoise.generate_schemas()
