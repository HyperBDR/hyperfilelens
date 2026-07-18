from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("protection", "0006_file_filter_rule_extended_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="backupconfigdirectory",
            name="path_type",
            field=models.CharField(
                choices=[
                    ("directory", "Directory"),
                    ("file", "File"),
                    ("unknown", "Unknown"),
                ],
                default="unknown",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="backupsourcesnapshotdirectory",
            name="path_type",
            field=models.CharField(
                choices=[
                    ("directory", "Directory"),
                    ("file", "File"),
                    ("unknown", "Unknown"),
                ],
                default="unknown",
                max_length=20,
            ),
        ),
    ]
