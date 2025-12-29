from tortoise.models import Model
from tortoise import fields



class SuperAdminSetting(Model):
    id = fields.IntField(primary_key = True)
    user = fields.ForeignKeyField("models.User" , related_name="super_admin_setting")
    max_call_duration = fields.IntField(null = True)
    max_calls = fields.IntField(null = True)
    transfer_rate = fields.FloatField(null = True)
    monthly_fee = fields.IntField(null = True)
    seconds_per_dollar = fields.FloatField(null=True)
    call_frequency = fields.IntField(default=10)
    call_period_minutes = fields.IntField(default=3)
    max_call_limit_free_trial=fields.IntField(default=2000)
    max_lead_limit_free_trial = fields.IntField(default=1000)


