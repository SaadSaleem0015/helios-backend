from models.super_admin_setting import SuperAdminSetting
from models.defaultSettings import DefaultSettings


async def user_settings(user):
    print(user.id)
    # check existing user settings
    settings = await SuperAdminSetting.filter(user=user).first()
    print(1)
    if not settings:
        print(2)

        # get default settings (assume only 1 record)
        default_settings = await DefaultSettings.first()
        print(3)
        
        # if no default row exists -> create one using model defaults
        if not default_settings:
            default_settings = await DefaultSettings.create()

        # create user settings using default values
        settings = await SuperAdminSetting.create(
            user=user,
            max_call_duration=default_settings.max_call_duration,
            max_calls=default_settings.max_calls,
            transfer_rate=default_settings.transfer_rate,
            monthly_fee=default_settings.monthly_fee,
            seconds_per_dollar=default_settings.seconds_per_dollar,
            call_frequency=default_settings.call_frequency,
            call_period_minutes=default_settings.call_period_minutes,
            max_call_limit_free_trial=default_settings.max_call_limit_free_trial,
            max_lead_limit_free_trial=default_settings.max_lead_limit_free_trial
        )

    return settings
