from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("restore", "0004_alter_restorerecorditem_status"),
        ("lens_bridge", "0022_workspace_binding"),
        ("node", "0006_node_network_inventory"),
    ]

    operations = [
        migrations.AddField(
            model_name="restorerecord",
            name="requesting_organization_id",
            field=models.BigIntegerField(db_index=True, default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="restorerecord",
            name="target_execution_organization_id",
            field=models.BigIntegerField(db_index=True, default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="restorerecord",
            name="target_execution_node_id",
            field=models.BigIntegerField(db_index=True, default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="restorerecord",
            name="purpose",
            field=models.CharField(
                choices=[("user_data", "User data"), ("lens_workspace", "Lens workspace")],
                db_index=True,
                default="user_data",
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="restorerecord",
            name="idempotency_key",
            field=models.CharField(blank=True, default="", max_length=160),
        ),
        migrations.AddField(
            model_name="restorerecord",
            name="workspace_binding_id",
            field=models.BigIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="restorerecord",
            constraint=models.UniqueConstraint(
                condition=Q(purpose="lens_workspace") & ~Q(idempotency_key=""),
                fields=("organization_id", "purpose", "idempotency_key"),
                name="uniq_restore_org_purpose_idem",
            ),
        ),
        migrations.AddConstraint(
            model_name="restorerecord",
            constraint=models.CheckConstraint(
                condition=(
                    Q(purpose="lens_workspace", workspace_binding_id__isnull=False)
                    & ~Q(idempotency_key="")
                    | Q(purpose="user_data", workspace_binding_id__isnull=True)
                ),
                name="restore_purpose_workspace_ck",
            ),
        ),
    ]
