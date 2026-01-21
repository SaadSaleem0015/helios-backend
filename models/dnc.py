from tortoise.models import Model
from tortoise import fields

class Dnc(Model):
    id = fields.IntField(primary_key=True)
    prompt = fields.TextField(null=True)