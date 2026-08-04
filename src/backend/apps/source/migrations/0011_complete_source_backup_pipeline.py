from django.db import migrations, models
from django.utils import timezone


TASK_STATUS = {
    "pending": "queued",
    "running": "running",
    "success": "success",
    "failed": "failed",
    "cancelled": "cancelled",
    "timeout": "timeout",
}


def _hostname(node):
    metadata = node.metadata if isinstance(node.metadata, dict) else {}
    inventory = metadata.get("inventory") if isinstance(metadata.get("inventory"), dict) else {}
    return str(inventory.get("hostname") or metadata.get("hostname") or node.name or "").strip()


def _ip(node):
    return str(node.ip_address or node.connection_ip_address or "").strip()


def _task(Task, TaskResource, organization_id, kind, ref_id, task_type):
    task = Task.objects.filter(
        organization_id=organization_id,
        task_type=task_type,
        resources__resource_type="backup_source",
        resources__resource_subtype=kind,
        resources__resource_id=ref_id,
    ).order_by("-created_at", "-id").first()
    if task is None:
        return "none", None
    return TASK_STATUS.get(task.status, "none"), task.id


def complete_source_backup_pipeline(apps, schema_editor):
    del schema_editor
    Node = apps.get_model("node", "Node")
    SourceResource = apps.get_model("source", "SourceResource")
    Pipeline = apps.get_model("source", "SourceBackupPipelineEntry")
    # Historical models do not keep SoftDeleteModel.all_objects unless
    # use_in_migrations=True; fall back to the default manager.
    pipeline_rows = getattr(Pipeline, "all_objects", Pipeline.objects)
    Task = apps.get_model("task", "Task")
    TaskResource = apps.get_model("task", "TaskResource")
    BackupConfig = apps.get_model("protection", "BackupConfig")
    active_keys = set()

    def upsert(kind, source, values):
        key = (source.organization_id, kind, source.id)
        active_keys.add(key)
        configured = BackupConfig.objects.filter(
            organization_id=source.organization_id,
            source_type=kind,
            source_ref_id=source.id,
            status__in=("active", "resetting", "reset_failed"),
        ).exists()
        row = pipeline_rows.filter(
            organization_id=source.organization_id, source_kind=kind, ref_id=source.id
        ).first()
        if row is None:
            Pipeline.objects.create(
                organization_id=source.organization_id,
                source_kind=kind,
                ref_id=source.id,
                step=3 if configured else 1,
                created_at=source.created_at,
                **values,
            )
            return
        # A pre-#293 soft-deleted row represented step 1 in the sparse model.
        step = 3 if configured else (row.step if not row.is_deleted and row.step in (1, 2, 3) else 1)
        for field, value in values.items():
            setattr(row, field, value)
        row.step = step
        row.created_at = source.created_at
        row.is_deleted = False
        row.deleted_at = None
        row.save()

    for node in Node.objects.filter(role="agent", is_deleted=False):
        backup_status, backup_id = _task(Task, TaskResource, node.organization_id, "agent", node.id, "backup")
        restore_status, restore_id = _task(Task, TaskResource, node.organization_id, "agent", node.id, "restore")
        upsert("agent", node, {
            "source_name": str(node.name or "").strip(),
            "source_hostname": _hostname(node),
            "source_ip": _ip(node),
            "source_status": str(node.status or ""),
            "source_availability": str(node.availability or "offline"),
            "last_backup_status": backup_status,
            "last_backup_task_id": backup_id,
            "last_restore_status": restore_status,
            "last_restore_task_id": restore_id,
        })
    for source in SourceResource.objects.filter(resource_type="nas", is_deleted=False).select_related("bound_node"):
        proxy = source.bound_node
        valid_proxy = proxy is not None and not proxy.is_deleted and proxy.role == "proxy"
        backup_status, backup_id = _task(Task, TaskResource, source.organization_id, "nas", source.id, "backup")
        restore_status, restore_id = _task(Task, TaskResource, source.organization_id, "nas", source.id, "restore")
        upsert("nas", source, {
            "source_name": str(source.name or "").strip(),
            "source_hostname": _hostname(proxy) if valid_proxy else "",
            "source_ip": _ip(proxy) if valid_proxy else "",
            "source_status": str(source.status or ""),
            "source_availability": str(source.availability or "offline") if valid_proxy else "offline",
            "last_backup_status": backup_status,
            "last_backup_task_id": backup_id,
            "last_restore_status": restore_status,
            "last_restore_task_id": restore_id,
        })
    now = timezone.now()
    for row in Pipeline.objects.filter(is_deleted=False):
        if (row.organization_id, row.source_kind, row.ref_id) not in active_keys:
            row.is_deleted = True
            row.deleted_at = now
            row.save(update_fields=["is_deleted", "deleted_at", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("node", "0009_node_availability"),
        ("protection", "0016_backup_config_repository_endpoint"),
        ("task", "0010_node_lifecycle_and_warning_step"),
        ("source", "0010_source_resource_availability"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sourcebackuppipelineentry",
            name="created_at",
            field=models.DateTimeField(default=timezone.now, editable=False),
        ),
        migrations.AddField(model_name="sourcebackuppipelineentry", name="source_name", field=models.CharField(blank=True, default="", max_length=255)),
        migrations.AddField(model_name="sourcebackuppipelineentry", name="source_hostname", field=models.CharField(blank=True, default="", max_length=255)),
        migrations.AddField(model_name="sourcebackuppipelineentry", name="source_ip", field=models.CharField(blank=True, default="", max_length=64)),
        migrations.AddField(model_name="sourcebackuppipelineentry", name="source_status", field=models.CharField(blank=True, default="", max_length=32)),
        migrations.AddField(model_name="sourcebackuppipelineentry", name="source_availability", field=models.CharField(choices=[("online", "Online"), ("offline", "Offline")], default="offline", max_length=20)),
        migrations.AddField(model_name="sourcebackuppipelineentry", name="last_backup_status", field=models.CharField(choices=[("none", "None"), ("queued", "Queued"), ("running", "Running"), ("stopping", "Stopping"), ("success", "Success"), ("failed", "Failed"), ("cancelled", "Cancelled"), ("timeout", "Timeout")], default="none", max_length=20)),
        migrations.AddField(model_name="sourcebackuppipelineentry", name="last_restore_status", field=models.CharField(choices=[("none", "None"), ("queued", "Queued"), ("running", "Running"), ("stopping", "Stopping"), ("success", "Success"), ("failed", "Failed"), ("cancelled", "Cancelled"), ("timeout", "Timeout")], default="none", max_length=20)),
        migrations.AddField(model_name="sourcebackuppipelineentry", name="last_backup_task_id", field=models.BigIntegerField(blank=True, null=True)),
        migrations.AddField(model_name="sourcebackuppipelineentry", name="last_restore_task_id", field=models.BigIntegerField(blank=True, null=True)),
        migrations.AlterModelOptions(name="sourcebackuppipelineentry", options={"ordering": ["-created_at", "-id"]}),
        migrations.RemoveIndex(model_name="sourcebackuppipelineentry", name="source_back_organiz_0f0f0f_idx"),
        migrations.RemoveIndex(model_name="sourcebackuppipelineentry", name="source_back_organiz_1a1a1a_idx"),
        migrations.AddIndex(model_name="sourcebackuppipelineentry", index=models.Index(condition=models.Q(("is_deleted", False)), fields=["organization", "step", "-created_at", "-id"], name="src_pipe_org_step_ord_idx")),
        migrations.AddIndex(model_name="sourcebackuppipelineentry", index=models.Index(condition=models.Q(("is_deleted", False)), fields=["organization", "source_status", "-created_at", "-id"], name="src_pipe_org_status_idx")),
        migrations.AddIndex(model_name="sourcebackuppipelineentry", index=models.Index(condition=models.Q(("is_deleted", False)), fields=["organization", "source_availability", "-created_at", "-id"], name="src_pipe_org_avail_idx")),
        migrations.AddIndex(model_name="sourcebackuppipelineentry", index=models.Index(condition=models.Q(("is_deleted", False)), fields=["organization", "last_backup_status", "-created_at", "-id"], name="src_pipe_org_bkstat_idx")),
        migrations.AddIndex(model_name="sourcebackuppipelineentry", index=models.Index(condition=models.Q(("is_deleted", False)), fields=["organization", "last_restore_status", "-created_at", "-id"], name="src_pipe_org_rststat_idx")),
        migrations.RunPython(complete_source_backup_pipeline, migrations.RunPython.noop),
    ]
