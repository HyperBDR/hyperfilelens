from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("iam", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="membership",
            name="preferred_feature",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Optional preferred feature key for landing path within this org.",
                max_length=50,
            ),
        ),
    ]

