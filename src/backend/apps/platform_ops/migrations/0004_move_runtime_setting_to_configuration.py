# Drop PlatformRuntimeSetting from platform_ops state (table owned by app_config).

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("platform_ops", "0003_rename_registration_runtime_setting"),
        ("app_config", "0003_platform_runtime_setting_state"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name="PlatformRuntimeSetting"),
            ],
            database_operations=[],
        ),
    ]
