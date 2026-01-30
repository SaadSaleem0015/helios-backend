from tortoise import fields
from tortoise.models import Model


class TwilioCredential(Model):
    """
    Stores Twilio credentials per user so each user can have
    their own Twilio account SID and auth token.
    """

    id = fields.IntField(pk=True)
    user = fields.OneToOneField(
        "models.User",
        related_name="twilio_credential",
        on_delete=fields.CASCADE,
    )
    account_sid = fields.CharField(max_length=255)
    auth_token = fields.CharField(max_length=255)
    address_sid = fields.CharField(max_length=255, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

