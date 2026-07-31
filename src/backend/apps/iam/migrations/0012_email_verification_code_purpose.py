from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("iam", "0011_oautherrorevent"),
    ]

    operations = [
        migrations.AddField(
            model_name="emailverificationcode",
            name="purpose",
            field=models.CharField(
                choices=[
                    ("legacy", "Legacy"),
                    ("registration", "Registration"),
                    ("password_reset", "Password reset"),
                    ("login", "Login"),
                ],
                db_index=True,
                default="legacy",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="emailverificationcode",
            name="failed_attempts",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="emailverificationcode",
            name="invalidated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="emailverificationcode",
            index=models.Index(
                fields=["user", "purpose", "is_used", "expires_at"],
                name="iam_email_code_purpose_idx",
            ),
        ),
    ]
