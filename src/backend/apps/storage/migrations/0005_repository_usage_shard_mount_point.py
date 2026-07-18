from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("storage", "0004_repository_usage_shard"),
    ]

    operations = [
        migrations.AddField(
            model_name="repositoryusageshard",
            name="mount_point",
            field=models.CharField(blank=True, default="", max_length=1000),
        ),
    ]
