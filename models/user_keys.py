from tortoise.models import Model
from tortoise import fields

class UserKeys(Model):
    id = fields.IntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", on_delete=fields.CASCADE)
    google_access_token  = fields.TextField(null=True)
    google_refresh_token = fields.TextField(null=True)
    google_token_expiry  = fields.DatetimeField(null=True)   # UTC
    google_email         = fields.CharField(max_length=255, null=True)
 
    sheet_id       = fields.CharField(max_length=500, null=True)
    sheet_tab_name = fields.CharField(max_length=255, null=True, default="Sheet1")
 
    webhook_secret = fields.CharField(max_length=64, null=True, unique=True)
 
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
  
  