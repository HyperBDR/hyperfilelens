from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lens_bridge", "0003_knowledge_source_ingest"),
    ]

    operations = [
        migrations.AddField(
            model_name="lenssessionlink",
            name="agent_model_ref",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
    ]
