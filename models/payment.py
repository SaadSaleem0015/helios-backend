from tortoise.models import Model
from tortoise import fields

class Payment(Model):
    id = fields.IntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="payments") 
    amount_paid = fields.FloatField()
    amount_received = fields.FloatField()
    name_on_card = fields.CharField(max_length=255 , null=True)
    address = fields.CharField(max_length=255,null=True)
    city = fields.CharField(max_length=100,null=True)
    state = fields.CharField(max_length=100,null=True)
    zip_code = fields.CharField(max_length=20,null=True)
    last4 = fields.CharField(max_length=4,null=True)
    expiration_date = fields.CharField(max_length=7,null=True)  
    token = fields.CharField(max_length=255,null=True)
    auto_replenishment = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)



