from tortoise.models import Model
from tortoise import fields

class ScheduleTime(Model):
    id = fields.IntField(pk=True) 
    from_time = fields.TimeField()
    to_time = fields.TimeField()
    day = fields.CharField(255)
    schedule = fields.ForeignKeyField("models.Schedule", related_name="schedule_times")