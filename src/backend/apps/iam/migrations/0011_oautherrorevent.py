from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("iam", "0010_profile_language_packs"),
    ]

    operations = [
        migrations.CreateModel(
            name="OAuthErrorEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "token_hash",
                    models.CharField(db_index=True, max_length=64, unique=True),
                ),
                (
                    "reason",
                    models.CharField(
                        choices=[
                            ("oauth_failed", "OAuth failed"),
                            ("state_lost", "OAuth state lost"),
                            ("invalid_grant", "Invalid OAuth grant"),
                            ("no_email", "Email unavailable"),
                            ("disabled", "OAuth disabled"),
                            ("not_authenticated", "Authentication incomplete"),
                            ("account_disabled", "Account disabled"),
                            ("provision_failed", "Provisioning failed"),
                        ],
                        max_length=32,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField(db_index=True)),
            ],
            options={
                "db_table": "iam_oauth_error_event",
                "ordering": ["-created_at", "id"],
            },
        ),
    ]
