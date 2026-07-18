from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("alerts", "0002_alert_center"),
    ]

    operations = [
        migrations.DeleteModel(
            name="AlertNotificationLog",
        ),
    ]
