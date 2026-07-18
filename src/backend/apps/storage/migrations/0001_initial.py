from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("iam", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Credential",
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
                ("organization_id", models.BigIntegerField(db_index=True)),
                (
                    "credential_type",
                    models.CharField(
                        choices=[
                            ("s3", "S3 Access Key"),
                            ("smb", "SMB User"),
                            ("repo_password", "Repository Password"),
                            ("api_token", "API Token"),
                        ],
                        max_length=30,
                    ),
                ),
                ("secret_cipher", models.JSONField(blank=True, default=dict)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "credential",
                "ordering": ["organization_id", "credential_type", "id"],
                "indexes": [
                    models.Index(
                        fields=["organization_id", "credential_type"],
                        name="credential_org_type_idx",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="Repository",
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
                ("organization_id", models.BigIntegerField(db_index=True)),
                ("name", models.CharField(max_length=200)),
                (
                    "repo_type",
                    models.CharField(
                        choices=[
                            ("s3", "S3"),
                            ("nas", "NAS"),
                            ("proxy_fs", "Proxy Filesystem"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("creating", "Creating"),
                            ("create_failed", "Create failed"),
                            ("created", "Created"),
                            ("removing", "Removing"),
                            ("remove_failed", "Remove failed"),
                            ("removed", "Removed"),
                        ],
                        db_index=True,
                        default="creating",
                        max_length=20,
                    ),
                ),
                (
                    "health",
                    models.CharField(
                        choices=[("online", "Online"), ("offline", "Offline")],
                        db_index=True,
                        default="offline",
                        max_length=20,
                    ),
                ),
                ("config", models.JSONField(blank=True, default=dict)),
                ("credential_id", models.BigIntegerField(blank=True, null=True)),
                ("capacity_bytes", models.BigIntegerField(default=0)),
                ("used_bytes", models.BigIntegerField(default=0)),
                ("last_checked_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                (
                    "nas_protocol",
                    models.CharField(
                        blank=True,
                        choices=[("smb", "SMB"), ("nfs", "NFS")],
                        max_length=20,
                        null=True,
                    ),
                ),
                (
                    "bind_node_type",
                    models.CharField(
                        blank=True,
                        choices=[("proxy", "Proxy")],
                        max_length=20,
                        null=True,
                    ),
                ),
                ("bind_node_id", models.BigIntegerField(blank=True, null=True)),
                (
                    "s3_platform",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("aws", "AWS"),
                            ("huawei", "Huawei"),
                            ("aliyun", "Aliyun"),
                            ("custom", "Custom"),
                        ],
                        max_length=50,
                        null=True,
                    ),
                ),
                ("s3_bucket", models.CharField(blank=True, max_length=100, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "storage_repository",
                "ordering": ["organization_id", "name", "id"],
                "indexes": [
                    models.Index(
                        fields=["organization_id", "repo_type", "status"],
                        name="storage_rep_organ_8d0473_idx",
                    ),
                    models.Index(
                        fields=["organization_id", "health"],
                        name="storage_rep_organ_fefeb5_idx",
                    ),
                    models.Index(
                        fields=["organization_id", "bind_node_type", "bind_node_id"],
                        name="storage_rep_organ_6f3912_idx",
                    ),
                    models.Index(
                        fields=["organization_id", "s3_platform", "s3_bucket"],
                        name="storage_rep_organ_93d157_idx",
                    ),
                ],
            },
        ),
    ]
