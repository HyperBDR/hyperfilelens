from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("notification", "0002_notification_log"),
    ]

    operations = [
        migrations.AlterModelTable(
            name="notificationchannel",
            table="notification_channels",
        ),
        migrations.AlterModelTable(
            name="notificationdelivery",
            table="notification_deliveries",
        ),
        migrations.AlterModelTable(
            name="notificationlog",
            table="notification_logs",
        ),
    ]
