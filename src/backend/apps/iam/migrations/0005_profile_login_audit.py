from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("iam", "0004_add_mfa_email_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="last_login_ip",
            field=models.CharField(blank=True, default="", max_length=45),
        ),
        migrations.AddField(
            model_name="profile",
            name="last_login_location",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="profile",
            name="previous_login_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="profile",
            name="previous_login_ip",
            field=models.CharField(blank=True, default="", max_length=45),
        ),
        migrations.AddField(
            model_name="profile",
            name="previous_login_location",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
    ]
