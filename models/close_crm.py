from tortoise import fields
from tortoise.models import Model
from models.user import User


class CloseCRM(Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="close_credentials")
    client_id = fields.CharField(max_length=255)
    client_secret = fields.TextField()          # Keep secret!
    access_token = fields.TextField(null=True)
    refresh_token = fields.TextField(null=True)
    expires_at = fields.DatetimeField(null=True)  # When access_token expires
    organization_id = fields.CharField(max_length=100, null=True)
    close_user_id = fields.CharField(max_length=100, null=True)  # Close user ID
    
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
  