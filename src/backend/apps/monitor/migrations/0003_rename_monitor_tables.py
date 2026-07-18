from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("monitor", "0002_resource_metric"),
    ]

    operations = [
        migrations.AlterModelTable(
            name="systemmetric",
            table="monitor_system_metrics",
        ),
        migrations.AlterModelTable(
            name="resourcemetric",
            table="monitor_resource_metrics",
        ),
    ]
