from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GlobalConfig",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("key", models.CharField(db_index=True, max_length=255)),
                (
                    "scope",
                    models.CharField(
                        choices=[("global", "Global"), ("tenant", "Tenant")],
                        db_index=True,
                        default="global",
                        max_length=20,
                    ),
                ),
                (
                    "tenant_key",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        default="",
                        max_length=128,
                    ),
                ),
                ("value", models.JSONField()),
                (
                    "value_type",
                    models.CharField(
                        choices=[
                            ("string", "String"),
                            ("number", "Number"),
                            ("boolean", "Boolean"),
                            ("object", "Object"),
                            ("array", "Array"),
                        ],
                        default="string",
                        max_length=20,
                    ),
                ),
                (
                    "category",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        default="",
                        max_length=100,
                    ),
                ),
                ("description", models.TextField(blank=True, default="")),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_app_configs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_app_configs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "app_config_globalconfig",
                "ordering": ["category", "key", "scope", "tenant_key", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="globalconfig",
            constraint=models.UniqueConstraint(
                fields=("key", "scope", "tenant_key"),
                name="uniq_app_config_key_scope_tenant",
            ),
        ),
    ]

