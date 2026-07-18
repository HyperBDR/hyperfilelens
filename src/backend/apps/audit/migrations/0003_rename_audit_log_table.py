from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0002_auditlog_correlation_resource"),
    ]

    operations = [
        migrations.AlterModelTable(
            name="auditlog",
            table="audit_logs",
        ),
    ]
