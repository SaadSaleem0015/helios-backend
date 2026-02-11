from tortoise.models import Model
from tortoise import fields
from enum import Enum


class TicketPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class SupportTicket(Model):
    id = fields.IntField(pk=True)

    # Auto ticket number → SUP-0001, SUP-0002 ...
    ticket_number = fields.CharField(max_length=20, unique=True)

    # Jo user ne ticket banaya
    user = fields.ForeignKeyField("models.User", related_name="support_tickets")

    subject = fields.CharField(max_length=255)
    description = fields.TextField()

    priority = fields.CharEnumField(TicketPriority, default=TicketPriority.MEDIUM)
    status = fields.CharEnumField(TicketStatus, default=TicketStatus.OPEN)

    # Admin ke liye
    admin_notes = fields.TextField(null=True, blank=True)
    resolved_by = fields.ForeignKeyField("models.User", related_name="resolved_tickets", null=True)

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

