from tortoise.models import Model
from tortoise import fields

class TermsAndConditions(Model):
    id = fields.IntField(pk=True)
    content = fields.TextField(null = True)  
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)  
    