from tortoise.models import Model
from tortoise import fields

class AutoReplenishment(Model):
    id = fields.IntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="replenishments") 
    replenishment = fields.BooleanField(default = False)



