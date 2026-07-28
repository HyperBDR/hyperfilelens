from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("storage", "0011_provider_catalog"),
    ]

    operations = [
        migrations.AddField(
            model_name="repository",
            name="s3_bucket_mode",
            field=models.CharField(
                choices=[
                    ("existing", "Existing bucket"),
                    ("new", "Bucket created for this repository"),
                ],
                default="existing",
                max_length=16,
            ),
        ),
    ]
