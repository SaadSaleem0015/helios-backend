from tortoise import fields
from tortoise.models import Model
from datetime import datetime
from pydantic import BaseModel
from enum import Enum


class UserType(Enum):
    ADMIN = "admin"
    USER = "user"

class User(Model):
    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=255)
    type = fields.CharEnumField(enum_type=UserType, max_length=6, default=UserType.USER)
    email = fields.CharField(max_length=255)
    email_verified = fields.BooleanField(default=False)
    password = fields.CharField(max_length=255)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    is_active = fields.BooleanField(default=True)
    criteria_approved = fields.BooleanField(default=False)
    submit_for_approval = fields.BooleanField(default=False)
    last_fee_deducted = fields.DatetimeField(null=True)
    fee_reminder_email = fields.BooleanField(default=False)
    fee_reminder_tries = fields.IntField(default=0)
    files: fields.ReverseRelation['File']
    settings: fields.ReverseRelation['Setting']
    documents: fields.ReverseRelation['Documents']
    call_logs = fields.ReverseRelation["CallLog"]
    time_limit = fields.ReverseRelation["TimeLimit"]







