from tortoise import fields, Model

class ZohoCRM(Model):
    id = fields.IntField(pk=True)
    client_id = fields.CharField(max_length=255)
    client_secret = fields.CharField(max_length=255)
    code = fields.CharField(max_length=255)
    access_token = fields.CharField(max_length=255, null=True)
    refresh_token = fields.CharField(max_length=255)
    api_domain = fields.CharField(max_length=255)
    user= fields.ForeignKeyField('models.User', related_name='zoho_crm')
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

