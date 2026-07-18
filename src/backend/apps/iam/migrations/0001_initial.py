from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Organization",
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
                    "key",
                    models.SlugField(
                        db_index=True,
                        help_text="Stable tenant key used in API requests.",
                        max_length=64,
                        unique=True,
                    ),
                ),
                ("name", models.CharField(max_length=200)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "iam_organization",
                "ordering": ["key", "id"],
            },
        ),
        migrations.CreateModel(
            name="PersonalApiKey",
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
                ("name", models.CharField(max_length=120)),
                ("token", models.CharField(db_index=True, max_length=64, unique=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="personal_api_keys",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "iam_personal_api_key",
                "ordering": ["-created_at", "id"],
            },
        ),
        migrations.CreateModel(
            name="Membership",
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
                    "role",
                    models.CharField(
                        choices=[
                            ("owner", "Owner"),
                            ("admin", "Admin"),
                            ("operator", "Operator"),
                            ("auditor", "Auditor"),
                        ],
                        db_index=True,
                        default="operator",
                        max_length=20,
                    ),
                ),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to="iam.organization",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "iam_membership",
            },
        ),
        migrations.AddConstraint(
            model_name="membership",
            constraint=models.UniqueConstraint(
                fields=("user", "organization"),
                name="uniq_iam_user_org",
            ),
        ),
        migrations.AddIndex(
            model_name="membership",
            index=models.Index(
                fields=["organization", "role", "is_active"],
                name="iam_member_organiza_9f4e5f_idx",
            ),
        ),
    ]

