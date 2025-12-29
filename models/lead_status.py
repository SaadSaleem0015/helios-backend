from tortoise.models import Model
from tortoise import fields



class LeadStatus(Model):
    id = fields.IntField(pk=True)
    schedule_call = fields.ForeignKeyField("models.ScheduleCall", related_name="lead_statuses")
    lead_id = fields.IntField()
    status = fields.CharField(max_length=20, default="Pending")
    ended_reason = fields.TextField(null=True)
    customer_name = fields.TextField(null=True)