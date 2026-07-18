# Generated manually for platform runtime settings

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("platform_ops", "0001_platform_audit_log"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlatformRuntimeSetting",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(db_index=True, max_length=128, unique=True)),
                ("value_text", models.TextField(blank=True, default="")),
                ("secret_ciphertext", models.TextField(blank=True, default="")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="platform_runtime_settings_updated",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "platform_runtime_settings",
                "ordering": ["key"],
            },
        ),
    ]
