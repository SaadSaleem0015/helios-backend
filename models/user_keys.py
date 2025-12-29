from tortoise.models import Model
from tortoise import fields

class UserKeys(Model):
    id = fields.IntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", on_delete=fields.CASCADE)
    ghl_key = fields.CharField(max_length=500)
