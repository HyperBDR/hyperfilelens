from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("node", "0004_alter_nodetoken_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="nodetoken",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="node_tokens_created",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="nodetoken",
            name="gateway_scope",
            field=models.CharField(blank=True, default="", max_length=16),
        ),
    ]
