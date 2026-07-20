from typing import Any

from django.db import migrations


OLD_KEY = "identity.registration_enabled"
NEW_KEY = "identity.email_signup_enabled"


def rename_registration_setting(apps: Any, schema_editor: Any) -> None:
    runtime_setting = apps.get_model("platform_ops", "PlatformRuntimeSetting")
    old_row = runtime_setting.objects.filter(key=OLD_KEY).first()
    if old_row is None:
        return

    if runtime_setting.objects.filter(key=NEW_KEY).exists():
        old_row.delete()
        return

    old_row.key = NEW_KEY
    old_row.save(update_fields=["key"])


def restore_registration_setting(apps: Any, schema_editor: Any) -> None:
    runtime_setting = apps.get_model("platform_ops", "PlatformRuntimeSetting")
    new_row = runtime_setting.objects.filter(key=NEW_KEY).first()
    if new_row is None:
        return

    if runtime_setting.objects.filter(key=OLD_KEY).exists():
        new_row.delete()
        return

    new_row.key = OLD_KEY
    new_row.save(update_fields=["key"])


class Migration(migrations.Migration):
    dependencies = [
        ("platform_ops", "0002_platform_runtime_setting"),
    ]

    operations = [
        migrations.RunPython(
            rename_registration_setting,
            restore_registration_setting,
        ),
    ]
