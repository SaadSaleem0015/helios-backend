from tortoise.models import Model
from tortoise import fields

class ScheduleCall(Model):
    id = fields.IntField(pk=True) 
    user = fields.ForeignKeyField("models.User") 
    vapi_assistant_id = fields.CharField(max_length=255, null=True) 
    title = fields.CharField(max_length=50, null=True) 
    date = fields.JSONField(default=[])
    file_id = fields.JSONField() 
    leads = fields.JSONField() 
    status = fields.CharField(max_length=50, default="pending")
    timeZone = fields.CharField(max_length=20 , null = True)
    call_id=fields.JSONField(default=[])
    lead_statuses: fields.ReverseRelation["LeadStatus"]
    schedule = fields.JSONField()
