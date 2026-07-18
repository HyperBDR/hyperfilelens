from django.db import migrations, models


def backfill_registered_at(apps, schema_editor):
    Profile = apps.get_model("iam", "Profile")
    for profile in Profile.objects.select_related("user").iterator():
        if profile.registered_at is None and profile.user.date_joined:
            profile.registered_at = profile.user.date_joined
            profile.save(update_fields=["registered_at"])


class Migration(migrations.Migration):

    dependencies = [
        ("iam", "0005_profile_login_audit"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="registered_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_registered_at, migrations.RunPython.noop),
    ]
