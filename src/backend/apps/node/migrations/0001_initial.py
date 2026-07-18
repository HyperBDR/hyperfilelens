"""Initial schema for the node app (Node, NodeToken, NodeTask)."""

import uuid

import django.db.models.deletion
from django.db import migrations, models

_NODE_ROLE_CHOICES = [
    ("source", "Source agent"),
    ("gateway", "Gateway"),
]

_NODE_STATUS_CHOICES = [
    ("online", "Online"),
    ("offline", "Offline"),
]

_NODE_TASK_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("running", "Running"),
    ("success", "Success"),
    ("failed", "Failed"),
    ("timeout", "Timeout"),
    ("canceled", "Canceled"),
]

_TIMESTAMP_FIELDS = [
    ("created_at", models.DateTimeField(auto_now_add=True)),
    ("updated_at", models.DateTimeField(auto_now=True)),
]

_SOFT_DELETE_FIELDS = [
    ("is_deleted", models.BooleanField(db_index=True, default=False)),
    (
        "deleted_at",
        models.DateTimeField(blank=True, db_index=True, null=True),
    ),
]

def _organization_field(related_name: str) -> tuple[str, models.ForeignKey]:
    return (
        "organization",
        models.ForeignKey(
            on_delete=django.db.models.deletion.CASCADE,
            related_name=related_name,
            to="iam.organization",
        ),
    )


def _org_scoped_fields(related_name: str) -> list:
    return [
        *_TIMESTAMP_FIELDS,
        *_SOFT_DELETE_FIELDS,
        _organization_field(related_name),
    ]


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("iam", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Node",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                *_org_scoped_fields("nodes"),
                ("name", models.CharField(max_length=200)),
                (
                    "role",
                    models.CharField(
                        choices=_NODE_ROLE_CHOICES,
                        max_length=20,
                    ),
                ),
                (
                    "version",
                    models.CharField(blank=True, default="", max_length=50),
                ),
                (
                    "os_name",
                    models.CharField(blank=True, default="", max_length=80),
                ),
                (
                    "ip_address",
                    models.GenericIPAddressField(blank=True, null=True),
                ),
                (
                    "status",
                    models.CharField(
                        choices=_NODE_STATUS_CHOICES,
                        db_index=True,
                        default="offline",
                        max_length=20,
                    ),
                ),
                (
                    "last_seen_at",
                    models.DateTimeField(blank=True, db_index=True, null=True),
                ),
                (
                    "metadata",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text=(
                            "Agent-reported extension data "
                            "(labels, env, install hints, etc.)."
                        ),
                    ),
                ),
            ],
            options={
                "db_table": "node_nodes",
                "ordering": ["organization_id", "name", "id"],
                "indexes": [
                    models.Index(
                        fields=["organization", "role", "status"],
                        name="node_nd_org_role_st_idx",
                    ),
                    models.Index(
                        fields=["organization", "last_seen_at"],
                        name="node_nd_org_seen_idx",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="NodeToken",
            fields=[
                (
                    "id",
                    models.BigAutoField(primary_key=True, serialize=False),
                ),
                *_org_scoped_fields("node_tokens"),
                (
                    "token",
                    models.CharField(
                        db_index=True,
                        max_length=64,
                        unique=True,
                    ),
                ),
                (
                    "role",
                    models.CharField(
                        choices=_NODE_ROLE_CHOICES,
                        max_length=20,
                    ),
                ),
                (
                    "note",
                    models.CharField(blank=True, default="", max_length=200),
                ),
                (
                    "is_active",
                    models.BooleanField(db_index=True, default=True),
                ),
                (
                    "expires_at",
                    models.DateTimeField(blank=True, db_index=True, null=True),
                ),
                ("used_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "db_table": "node_tokens",
                "ordering": ["-created_at", "id"],
                "indexes": [
                    models.Index(
                        fields=["organization", "role", "is_active"],
                        name="node_tkn_org_role_act_idx",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="NodeTask",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                *_org_scoped_fields("node_tasks"),
                (
                    "correlation_type",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        default="",
                        max_length=80,
                    ),
                ),
                (
                    "correlation_id",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        default="",
                        max_length=128,
                    ),
                ),
                ("kind", models.CharField(db_index=True, max_length=120)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("result", models.JSONField(blank=True, default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=_NODE_TASK_STATUS_CHOICES,
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                (
                    "dispatched_at",
                    models.DateTimeField(blank=True, db_index=True, null=True),
                ),
                (
                    "last_progress_at",
                    models.DateTimeField(blank=True, db_index=True, null=True),
                ),
                (
                    "watchdog_deadline_at",
                    models.DateTimeField(db_index=True),
                ),
                ("last_error", models.TextField(blank=True, default="")),
                (
                    "node",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="node_tasks",
                        to="node.node",
                    ),
                ),
            ],
            options={
                "db_table": "node_tasks",
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(
                        fields=["created_at"],
                        name="node_tasks_created_at_idx",
                    ),
                    models.Index(
                        fields=[
                            "organization",
                            "status",
                            "watchdog_deadline_at",
                        ],
                        name="node_tsk_org_st_wd_idx",
                    ),
                    models.Index(
                        fields=["node", "status"],
                        name="node_tsk_node_st_idx",
                    ),
                    models.Index(
                        fields=["correlation_type", "correlation_id"],
                        name="node_tsk_corr_idx",
                    ),
                ],
            },
        ),
    ]
