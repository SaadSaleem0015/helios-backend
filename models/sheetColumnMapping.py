from tortoise.models import Model
from tortoise import fields


class SheetColumnMapping(Model):
    """
    Stores which column letter (A, B, C …) each system field maps to
    in the user's Google Sheet.

    null column = user does not want that field exported.

    Example row:
        first_name_col        = "A"
        last_name_col         = "B"
        phone_number_col      = "C"
        address_col           = null   ← not collected in this user's script
        city_col              = "D"
        job_description_col   = null
        call_ended_reason_col = "E"
        call_datetime_col     = "F"
    """

    id   = fields.IntField(primary_key=True)
    user = fields.ForeignKeyField(
        "models.User",
        on_delete=fields.CASCADE,
        related_name="sheet_mapping",
    )

    # Every field is nullable – null means "skip this column"
    first_name_col        = fields.CharField(max_length=5, null=True)
    last_name_col         = fields.CharField(max_length=5, null=True)
    phone_number_col      = fields.CharField(max_length=5, null=True)
    address_col           = fields.CharField(max_length=5, null=True)
    city_col              = fields.CharField(max_length=5, null=True)
    job_description_col   = fields.CharField(max_length=5, null=True)
    call_ended_reason_col = fields.CharField(max_length=5, null=True)
    call_datetime_col     = fields.CharField(max_length=5, null=True)

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "sheet_column_mappings"