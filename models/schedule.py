from tortoise.models import Model
from tortoise import fields

class Schedule(Model):
    id = fields.IntField(pk=True) 
    user = fields.ForeignKeyField("models.User", related_name="schedules")
    title = fields.CharField(255)
    timezone = fields.CharField(255)
    schedule_times: fields.ReverseRelation["ScheduleTime"]
    complete_schedule = fields.JSONField()