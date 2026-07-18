import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("iam", "0001_initial"),
        ("node", "0003_node_role_agent_proxy_gateway"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SourceResource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("deleted_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                ("resource_type", models.CharField(db_index=True, default="nfs", max_length=20)),
                ("config", models.JSONField(blank=True, default=dict)),
                ("credentials", models.JSONField(blank=True, default=dict)),
                ("mount_status", models.CharField(default="unmounted", max_length=20)),
                ("mount_point", models.CharField(blank=True, default="", max_length=512)),
                ("mount_error", models.TextField(blank=True, default="")),
                ("status", models.CharField(db_index=True, default="active", max_length=20)),
                ("status_message", models.TextField(blank=True, default="")),
                ("last_connection_test", models.DateTimeField(blank=True, null=True)),
                ("connection_test_result", models.TextField(blank=True, default="")),
                ("total_size", models.BigIntegerField(default=0)),
                ("used_size", models.BigIntegerField(default=0)),
                ("free_size", models.BigIntegerField(default=0)),
                ("file_count", models.BigIntegerField(default=0)),
                (
                    "bound_node",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="source_resources",
                        to="node.node",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_source_resources",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="source_resources",
                        to="iam.organization",
                    ),
                ),
            ],
            options={
                "db_table": "source_resource",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="sourceresource",
            index=models.Index(fields=["organization", "resource_type"], name="src_res_org_type_idx"),
        ),
        migrations.AddIndex(
            model_name="sourceresource",
            index=models.Index(fields=["organization", "status"], name="src_res_org_status_idx"),
        ),
        migrations.AddIndex(
            model_name="sourceresource",
            index=models.Index(fields=["bound_node"], name="src_res_bound_node_idx"),
        ),
        migrations.AddConstraint(
            model_name="sourceresource",
            constraint=models.UniqueConstraint(fields=("organization", "name"), name="uniq_source_resource_org_name"),
        ),
    ]
