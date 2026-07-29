from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("source", "0005_alter_sourceresource_mount_status_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sourceresource",
            name="status",
            field=models.CharField(
                choices=[
                    ("active", "Active"),
                    ("inactive", "Inactive"),
                    ("error", "Error"),
                    ("removing", "Removing"),
                    ("remove_failed", "Remove failed"),
                    ("removed", "Removed"),
                ],
                db_index=True,
                default="active",
                max_length=20,
            ),
        ),
        migrations.RemoveConstraint(
            model_name="sourceresource",
            name="uniq_source_resource_org_name",
        ),
        migrations.AddConstraint(
            model_name="sourceresource",
            constraint=models.UniqueConstraint(
                condition=models.Q(is_deleted=False),
                fields=("organization", "name"),
                name="uniq_source_resource_org_name",
            ),
        ),
    ]
