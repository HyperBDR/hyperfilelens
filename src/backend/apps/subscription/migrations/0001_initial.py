from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("iam", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Plan",
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
                ("key", models.CharField(max_length=80, unique=True)),
                ("name", models.CharField(max_length=200)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("spec", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "subscription_plan",
                "ordering": ["key"],
            },
        ),
        migrations.CreateModel(
            name="OrganizationSubscription",
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
                ("status", models.CharField(db_index=True, default="active", max_length=30)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("ends_at", models.DateTimeField(blank=True, null=True)),
                ("overrides", models.JSONField(blank=True, default=dict)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "organization",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subscription",
                        to="iam.organization",
                    ),
                ),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="org_subscriptions",
                        to="subscription.plan",
                    ),
                ),
            ],
            options={
                "db_table": "subscription_org",
            },
        ),
        migrations.CreateModel(
            name="Entitlement",
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
                ("key", models.CharField(db_index=True, max_length=120)),
                ("enabled", models.BooleanField(db_index=True, default=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="entitlements",
                        to="iam.organization",
                    ),
                ),
            ],
            options={
                "db_table": "subscription_entitlement",
            },
        ),
        migrations.AddConstraint(
            model_name="entitlement",
            constraint=models.UniqueConstraint(
                fields=("organization", "key"),
                name="uniq_subscription_entitlement_org_key",
            ),
        ),
        migrations.CreateModel(
            name="Quota",
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
                ("key", models.CharField(db_index=True, max_length=120)),
                ("limit", models.BigIntegerField(default=0)),
                ("unit", models.CharField(default="count", max_length=30)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="quotas",
                        to="iam.organization",
                    ),
                ),
            ],
            options={
                "db_table": "subscription_quota",
            },
        ),
        migrations.AddConstraint(
            model_name="quota",
            constraint=models.UniqueConstraint(
                fields=("organization", "key"),
                name="uniq_subscription_quota",
            ),
        ),
        migrations.CreateModel(
            name="UsageCounter",
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
                ("key", models.CharField(db_index=True, max_length=120)),
                ("value", models.BigIntegerField(default=0)),
                ("window", models.CharField(db_index=True, default="lifetime", max_length=30)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="usage_counters",
                        to="iam.organization",
                    ),
                ),
            ],
            options={
                "db_table": "subscription_usage",
            },
        ),
        migrations.AddConstraint(
            model_name="usagecounter",
            constraint=models.UniqueConstraint(
                fields=("organization", "key", "window"),
                name="uniq_subscription_usage",
            ),
        ),
    ]

