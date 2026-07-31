from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("node", "0007_nodetask_delivery_ack"),
    ]

    operations = [
        migrations.AddField(
            model_name="nodetask",
            name="requesting_organization_id",
            field=models.BigIntegerField(db_index=True, default=0),
            preserve_default=False,
        ),
    ]
