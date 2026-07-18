from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("storage", "0002_repository_usage_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="repository",
            name="health",
            field=models.CharField(
                choices=[
                    ("online", "Online"),
                    ("offline", "Offline"),
                    ("unverified", "Unverified"),
                ],
                db_index=True,
                default="offline",
                max_length=20,
            ),
        ),
    ]
