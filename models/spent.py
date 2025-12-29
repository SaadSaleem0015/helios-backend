from tortoise.models import Model
from tortoise import fields

class Spent(Model):
    id = fields.IntField(primary_key=True)
    user = fields.ForeignKeyField('models.User')
    description=fields.CharField(max_length=250)
    spent_money=fields.FloatField(null = True)
    created_at = fields.DatetimeField(auto_now_add=True)