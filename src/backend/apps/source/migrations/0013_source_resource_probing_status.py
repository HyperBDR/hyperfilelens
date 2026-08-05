from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("source", "0012_backup_pipeline_query_indexes")]

    operations = [
        migrations.AlterField(
            model_name="sourceresource",
            name="status",
            field=models.CharField(
                choices=[
                    ("active", "Active"),
                    ("inactive", "Inactive"),
                    ("error", "Error"),
                    ("probing", "Probing"),
                    ("removing", "Removing"),
                    ("remove_failed", "Remove failed"),
                    ("removed", "Removed"),
                ],
                db_index=True,
                default="active",
                max_length=20,
            ),
        ),
    ]
