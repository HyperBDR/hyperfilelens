from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lens_bridge", "0023_session_teardown_state"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="lensgatewaylink",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(is_platform_default=False)
                    | models.Q(scope="platform")
                ),
                name="lens_brgw_default_scope_ck",
            ),
        ),
        migrations.AddConstraint(
            model_name="lensgatewaylink",
            constraint=models.UniqueConstraint(
                fields=("organization",),
                condition=models.Q(
                    scope="platform",
                    is_platform_default=True,
                    is_deleted=False,
                ),
                name="uniq_lens_brgw_org_default",
            ),
        ),
    ]
