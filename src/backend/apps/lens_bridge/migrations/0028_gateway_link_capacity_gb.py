from django.db import migrations, models


def copy_legacy_instance_capacity(apps, schema_editor):
    """Seed each platform gateway link from the old instance-wide setting."""
    Link = apps.get_model("lens_bridge", "LensGatewayLink")
    Setting = None
    # Runtime settings moved platform_ops → app_config; accept either historical label.
    for app_label in ("app_config", "platform_ops"):
        try:
            Setting = apps.get_model(app_label, "PlatformRuntimeSetting")
            break
        except LookupError:
            continue
    if Setting is None:
        return
    row = Setting.objects.filter(key="gateway.public_total_capacity_gb").first()
    if row is None:
        return
    try:
        value = int(str(row.value_text).strip())
    except (TypeError, ValueError, AttributeError):
        return
    if value < -1:
        return
    Link.objects.filter(scope="platform").update(capacity_gb=value)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("lens_bridge", "0027_document_conversion_and_multimodal_defaults"),
        ("platform_ops", "0002_platform_runtime_setting"),
    ]

    operations = [
        migrations.AddField(
            model_name="lensgatewaylink",
            name="capacity_gb",
            field=models.IntegerField(default=-1),
        ),
        migrations.RunPython(copy_legacy_instance_capacity, noop_reverse),
    ]
