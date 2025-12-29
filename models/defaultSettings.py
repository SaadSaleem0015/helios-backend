from tortoise.models import Model
from tortoise import fields



class DefaultSettings(Model):
    id = fields.IntField(primary_key = True)
    max_call_duration = fields.IntField(null = True, default = 100)
    max_calls = fields.IntField(null = True, default = 50)
    transfer_rate = fields.FloatField(null = True, default = 2)
    monthly_fee = fields.IntField(null = True, default = 100)
    phone_number_price = fields.IntField(null = True, default = 5) 
    seconds_per_dollar = fields.FloatField(null = True, default= 60)
    call_frequency = fields.IntField(default=10)
    call_period_minutes = fields.IntField(default=3)
    max_call_limit_free_trial=fields.IntField(default=2000)
    max_lead_limit_free_trial = fields.IntField(default=3000)
   