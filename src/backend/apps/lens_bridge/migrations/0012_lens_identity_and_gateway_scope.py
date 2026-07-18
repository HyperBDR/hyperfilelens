from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("lens_bridge", "0011_lenssessionlink_active_run"),
    ]

    operations = [
        migrations.AddField(
            model_name="lensgatewaylink",
            name="scope",
            field=models.CharField(
                choices=[("platform", "Platform"), ("tenant", "Tenant")],
                db_index=True,
                default="tenant",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="lensgatewaylink",
            name="is_platform_default",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddIndex(
            model_name="lensgatewaylink",
            index=models.Index(
                fields=["scope", "is_platform_default"],
                name="lens_brgw_scope_def_idx",
            ),
        ),
        migrations.CreateModel(
            name="LensSlUserLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sl_user_id", models.IntegerField(db_index=True)),
                ("sl_username", models.CharField(max_length=150)),
                ("gateway_operator", models.BooleanField(default=False)),
                (
                    "provision_status",
                    models.CharField(
                        choices=[("ready", "Ready"), ("pending", "Pending"), ("error", "Error")],
                        db_index=True,
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("last_error", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "hfl_user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lens_sl_user_link",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "lens_bridge_sl_user_link",
            },
        ),
        migrations.AddIndex(
            model_name="lenssluserlink",
            index=models.Index(fields=["sl_user_id"], name="lens_bslusr_sl_uid_idx"),
        ),
        migrations.CreateModel(
            name="LensChatBinding",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("backup_config_id", models.BigIntegerField(db_index=True)),
                ("backup_source_snapshot_id", models.BigIntegerField(db_index=True)),
                ("backup_snapshot_directory_id", models.BigIntegerField(blank=True, db_index=True, null=True)),
                ("source_path", models.CharField(blank=True, default="", max_length=500)),
                ("sl_assistant_uuid", models.UUIDField(blank=True, db_index=True, null=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                (
                    "gateway_link",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="chat_bindings",
                        to="lens_bridge.lensgatewaylink",
                    ),
                ),
                (
                    "hfl_user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lens_chat_bindings",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "knowledge_source",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="chat_bindings",
                        to="lens_bridge.lensknowledgesource",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(class)s_set",
                        to="iam.organization",
                    ),
                ),
            ],
            options={
                "db_table": "lens_bridge_chat_binding",
                "ordering": ["-updated_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="lenschatbinding",
            index=models.Index(
                fields=["organization", "hfl_user", "is_active"],
                name="lens_bcb_org_user_act_idx",
            ),
        ),
        migrations.AddField(
            model_name="lenssessionlink",
            name="chat_binding",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="session_links",
                to="lens_bridge.lenschatbinding",
            ),
        ),
    ]
