# Generated for restore domain initial rebuild.

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="RestorePlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("organization_id", models.BigIntegerField(db_index=True)),
                ("backup_config_id", models.BigIntegerField(db_index=True)),
                ("backup_config_dir_id", models.BigIntegerField(db_index=True)),
                ("source_type", models.CharField(choices=[("agent", "Agent"), ("nas", "NAS")], max_length=16)),
                ("source_ref_id", models.BigIntegerField()),
                ("source_path", models.CharField(max_length=1000)),
                ("target_type", models.CharField(choices=[("agent", "Agent"), ("nas", "NAS")], max_length=16)),
                ("target_ref_id", models.BigIntegerField()),
                ("restore_dir", models.CharField(max_length=1000)),
                ("conflict_mode", models.CharField(choices=[("skip", "Skip"), ("overwrite", "Overwrite")], max_length=16)),
                ("enabled", models.BooleanField(db_index=True, default=True)),
                ("sort_order", models.IntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "restore_plan",
                "ordering": ["source_type", "source_ref_id", "sort_order", "id"],
            },
        ),
        migrations.CreateModel(
            name="RestoreRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("organization_id", models.BigIntegerField(db_index=True)),
                ("restore_uid", models.CharField(max_length=64)),
                ("source_mode", models.CharField(choices=[("plan", "Plan"), ("manual", "Manual")], db_index=True, max_length=16)),
                ("plan_id", models.BigIntegerField(blank=True, db_index=True, null=True)),
                ("task_id", models.BigIntegerField(db_index=True)),
                ("task_uuid", models.UUIDField(db_index=True, default=uuid.uuid4)),
                ("source_type", models.CharField(choices=[("agent", "Agent"), ("nas", "NAS")], max_length=16)),
                ("source_ref_id", models.BigIntegerField()),
                ("backup_config_id", models.BigIntegerField(blank=True, db_index=True, null=True)),
                ("source_snapshot_id", models.BigIntegerField(db_index=True)),
                ("target_type", models.CharField(choices=[("agent", "Agent"), ("nas", "NAS")], max_length=16)),
                ("target_ref_id", models.BigIntegerField()),
                ("target_path", models.CharField(max_length=1000)),
                ("scope", models.CharField(choices=[("snapshot", "Snapshot"), ("paths", "Paths")], max_length=16)),
                ("conflict_mode", models.CharField(choices=[("skip", "Skip"), ("overwrite", "Overwrite")], max_length=16)),
                ("request_payload", models.JSONField(blank=True, default=dict)),
                ("expanded_payload", models.JSONField(blank=True, default=dict)),
                ("created_by_id", models.BigIntegerField(blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "restore_record",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="RestoreRecordItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("organization_id", models.BigIntegerField(db_index=True)),
                ("source_snapshot_directory_id", models.BigIntegerField(db_index=True)),
                ("backup_config_dir_id", models.BigIntegerField(db_index=True)),
                ("repository_id", models.BigIntegerField(db_index=True)),
                ("kopia_snapshot_id", models.CharField(db_index=True, max_length=128)),
                ("source_path", models.CharField(max_length=1000)),
                ("selected_paths", models.JSONField(blank=True, default=list)),
                ("target_path", models.CharField(max_length=1000)),
                ("conflict_mode", models.CharField(choices=[("skip", "Skip"), ("overwrite", "Overwrite")], max_length=16)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("running", "Running"), ("success", "Success"), ("failed", "Failed"), ("skipped", "Skipped")], db_index=True, default="pending", max_length=32)),
                ("result_payload", models.JSONField(blank=True, default=dict)),
                ("error_code", models.CharField(blank=True, default="", max_length=80)),
                ("error_message", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("restore_record", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="restore.restorerecord")),
            ],
            options={
                "db_table": "restore_record_item",
                "ordering": ["restore_record_id", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="restoreplan",
            index=models.Index(fields=["organization_id", "source_type", "source_ref_id"], name="restore_plan_org_src_idx"),
        ),
        migrations.AddIndex(
            model_name="restoreplan",
            index=models.Index(fields=["organization_id", "target_type", "target_ref_id"], name="restore_plan_org_tgt_idx"),
        ),
        migrations.AddIndex(
            model_name="restorerecord",
            index=models.Index(fields=["organization_id", "created_at"], name="restore_rec_org_cr_idx"),
        ),
        migrations.AddIndex(
            model_name="restorerecord",
            index=models.Index(fields=["organization_id", "source_type", "source_ref_id", "created_at"], name="restore_rec_org_src_cr_idx"),
        ),
        migrations.AddIndex(
            model_name="restorerecord",
            index=models.Index(fields=["organization_id", "target_type", "target_ref_id"], name="restore_rec_org_tgt_idx"),
        ),
        migrations.AddConstraint(
            model_name="restorerecord",
            constraint=models.UniqueConstraint(fields=("organization_id", "restore_uid"), name="uniq_restore_record_uid"),
        ),
        migrations.AddConstraint(
            model_name="restorerecorditem",
            constraint=models.UniqueConstraint(fields=("restore_record", "source_snapshot_directory_id", "target_path"), name="uniq_restore_item_dir_target"),
        ),
    ]
