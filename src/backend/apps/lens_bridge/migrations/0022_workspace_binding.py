import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("lens_bridge", "0021_knowledge_source_gateway_link"),
    ]

    operations = [
        migrations.AlterField(
            model_name="lensknowledgesource",
            name="gateway_link",
            field=models.ForeignKey(
                help_text="Authoritative gateway authorization used for execution.",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="knowledge_sources",
                to="lens_bridge.lensgatewaylink",
            ),
        ),
        migrations.AddConstraint(
            model_name="lensgatewaylink",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(scope="platform", owner_user_id__isnull=True)
                    | models.Q(scope="user", owner_user_id__isnull=False)
                ),
                name="lens_brgw_scope_owner_ck",
            ),
        ),
        migrations.CreateModel(
            name="LensWorkspaceBinding",
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
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                (
                    "deleted_at",
                    models.DateTimeField(blank=True, db_index=True, null=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "workspace_uid",
                    models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                ("execution_organization_id", models.BigIntegerField(db_index=True)),
                ("execution_node_id", models.BigIntegerField(db_index=True)),
                (
                    "workspace_kind",
                    models.CharField(
                        choices=[
                            ("managed_restore", "Managed restore"),
                            ("gateway_local", "Gateway local"),
                        ],
                        db_index=True,
                        max_length=24,
                    ),
                ),
                ("workspace_root", models.CharField(max_length=500)),
                (
                    "relative_path",
                    models.CharField(blank=True, default="", max_length=500),
                ),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("preparing", "Preparing"),
                            ("ready", "Ready"),
                            ("deleting", "Deleting"),
                            ("deleted", "Deleted"),
                            ("error", "Error"),
                        ],
                        db_index=True,
                        default="preparing",
                        max_length=16,
                    ),
                ),
                (
                    "identity_status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("ready", "Ready"),
                            ("not_applicable", "Not applicable"),
                            ("error", "Error"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=24,
                    ),
                ),
                ("last_error", models.TextField(blank=True, default="")),
                (
                    "gateway_link",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="workspace_bindings",
                        to="lens_bridge.lensgatewaylink",
                    ),
                ),
                (
                    "knowledge_source",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="workspace_binding",
                        to="lens_bridge.lensknowledgesource",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="iam.organization",
                    ),
                ),
            ],
            options={"db_table": "lens_bridge_workspace_binding"},
        ),
        migrations.AddConstraint(
            model_name="lensworkspacebinding",
            constraint=models.UniqueConstraint(
                condition=~models.Q(relative_path=""),
                fields=("gateway_link", "relative_path"),
                name="uniq_lens_workspace_link_path",
            ),
        ),
        migrations.AddConstraint(
            model_name="lensworkspacebinding",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        workspace_kind="managed_restore",
                        relative_path__gt="",
                        identity_status__in=["pending", "ready", "error"],
                    )
                    | models.Q(
                        workspace_kind="gateway_local",
                        relative_path="",
                        identity_status="not_applicable",
                    )
                ),
                name="lens_bws_kind_path_identity_ck",
            ),
        ),
        migrations.AddIndex(
            model_name="lensworkspacebinding",
            index=models.Index(
                fields=["organization", "state"],
                name="lens_bws_org_state_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="lensworkspacebinding",
            index=models.Index(
                fields=["execution_node_id", "state"],
                name="lens_bws_node_state_idx",
            ),
        ),
    ]
