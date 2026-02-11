from tortoise import fields, models
from tortoise.contrib.pydantic import pydantic_model_creator

class CalComIntegration(models.Model):
    """
    Stores Cal.com API key + selected event type per user.
    One active integration per user (we can enforce uniqueness or allow multiple later).
    """
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="cal_integrations")  # assuming you have a User model
    api_key = fields.CharField(max_length=255)  # cal_live_xxxx...
    event_type_id = fields.IntField()
    slug = fields.CharField(max_length=100)
    time_zone = fields.CharField(max_length=100)  # e.g. "Europe/London" or "Asia/Karachi"
    event_name = fields.CharField(max_length=255, null=True)  # optional: title from Cal.com
    length_minutes = fields.IntField(null=True)  # optional: duration
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    is_active = fields.BooleanField(default=True)
