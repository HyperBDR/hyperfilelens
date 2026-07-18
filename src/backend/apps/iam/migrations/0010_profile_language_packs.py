from django.db import migrations, models


def normalize_profile_preferences(apps, schema_editor) -> None:
    """Set existing profiles to the built-in locale-neutral defaults."""
    profile = apps.get_model("iam", "Profile")
    profile.objects.exclude(language="en").update(language="en")
    profile.objects.filter(timezone="Asia/Shanghai").update(timezone="UTC")


class Migration(migrations.Migration):
    dependencies = [
        ("iam", "0009_remove_membership_uniq_iam_user_org_and_more"),
    ]

    operations = [
        migrations.RunPython(normalize_profile_preferences, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="profile",
            name="language",
            field=models.CharField(default="en", max_length=32),
        ),
        migrations.AlterField(
            model_name="profile",
            name="timezone",
            field=models.CharField(default="UTC", max_length=50),
        ),
    ]
