from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("iam", "0006_profile_registered_at"),
    ]

    operations = [
        migrations.DeleteModel(
            name="Role",
        ),
    ]
