from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def convert_tenant_scope(apps, schema_editor):
    GatewayLink = apps.get_model("lens_bridge", "LensGatewayLink")
    GatewayLink.objects.filter(scope="tenant").update(scope="user")


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("lens_bridge", "0013_session_chat_lifecycle"),
    ]

    operations = [
        migrations.AddField(
            model_name="lensgatewaylink",
            name="origin",
            field=models.CharField(
                choices=[
                    ("user", "User"),
                    ("platform", "Platform"),
                    ("external", "External"),
                    ("system", "System"),
                ],
                db_index=True,
                default="user",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="lensgatewaylink",
            name="owner_user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="lens_gateway_links_owned",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="lensgatewaylink",
            name="scope",
            field=models.CharField(
                choices=[("platform", "Platform"), ("user", "User")],
                db_index=True,
                default="user",
                max_length=16,
            ),
        ),
        migrations.RunPython(convert_tenant_scope, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="lensgatewaylink",
            name="sl_lensnode_uuid",
            field=models.UUIDField(blank=True, null=True, unique=True),
        ),
    ]
