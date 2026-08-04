from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.operations import AddIndexConcurrently, TrigramExtension
from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False
    dependencies = [
        ("source", "0011_complete_source_backup_pipeline"),
    ]

    operations = [
        TrigramExtension(),
        AddIndexConcurrently(
            model_name="sourcebackuppipelineentry",
            index=GinIndex(
                fields=["source_name"],
                name="src_pipe_name_trgm_idx",
                opclasses=["gin_trgm_ops"],
                condition=models.Q(("is_deleted", False)),
            ),
        ),
        AddIndexConcurrently(
            model_name="sourcebackuppipelineentry",
            index=GinIndex(
                fields=["source_hostname"],
                name="src_pipe_host_trgm_idx",
                opclasses=["gin_trgm_ops"],
                condition=models.Q(("is_deleted", False)),
            ),
        ),
        AddIndexConcurrently(
            model_name="sourcebackuppipelineentry",
            index=models.Index(
                fields=["source_ip"],
                name="src_pipe_ip_prefix_idx",
                opclasses=["varchar_pattern_ops"],
                condition=models.Q(("is_deleted", False)),
            ),
        ),
        AddIndexConcurrently(
            model_name="sourcebackuppipelineentry",
            index=models.Index(
                fields=["organization", "step", "source_status", "-created_at", "-id"],
                name="src_pipe_step_status_idx",
                condition=models.Q(("is_deleted", False)),
            ),
        ),
        AddIndexConcurrently(
            model_name="sourcebackuppipelineentry",
            index=models.Index(
                fields=["organization", "step", "source_availability", "-created_at", "-id"],
                name="src_pipe_step_avail_idx",
                condition=models.Q(("is_deleted", False)),
            ),
        ),
        AddIndexConcurrently(
            model_name="sourcebackuppipelineentry",
            index=models.Index(
                fields=["organization", "step", "last_backup_status", "-created_at", "-id"],
                name="src_pipe_step_bkstat_idx",
                condition=models.Q(("is_deleted", False)),
            ),
        ),
        AddIndexConcurrently(
            model_name="sourcebackuppipelineentry",
            index=models.Index(
                fields=["organization", "step", "last_restore_status", "-created_at", "-id"],
                name="src_pipe_step_rststat_idx",
                condition=models.Q(("is_deleted", False)),
            ),
        ),
    ]
