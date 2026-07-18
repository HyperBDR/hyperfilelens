from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="auditlog",
            name="correlation_id",
            field=models.CharField(blank=True, db_index=True, default="", max_length=36),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="resource_id",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="resource_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="resource_type",
            field=models.CharField(blank=True, db_index=True, default="", max_length=120),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["correlation_id"], name="audit_corr_id_idx"),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["resource_type", "resource_id"], name="audit_resource_idx"),
        ),
    ]
