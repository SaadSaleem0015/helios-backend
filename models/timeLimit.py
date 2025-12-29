from tortoise.models import Model
from tortoise import fields

class TimeLimit(Model):
    id = fields.IntField(primary_key=True)
    seconds = fields.FloatField()
    user = fields.ForeignKeyField("models.User",  related_name="time_limit")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

  
    
