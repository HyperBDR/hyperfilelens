from django.db import models

from apps.iam.models import Organization


class Plan(models.Model):
    key = models.CharField(max_length=80, unique=True)
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True, db_index=True)
    spec = models.JSONField(default=dict, blank=True)  # entitlements + quotas template
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "subscription_plan"
        ordering = ["key"]


class OrganizationSubscription(models.Model):
    organization = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name="org_subscriptions",
    )
    status = models.CharField(max_length=30, default="active", db_index=True)
    started_at = models.DateTimeField(blank=True, null=True)
    ends_at = models.DateTimeField(blank=True, null=True)
    overrides = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "subscription_org"


class Entitlement(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="entitlements",
    )
    key = models.CharField(max_length=120, db_index=True)
    enabled = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "subscription_entitlement"
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "key"],
                name="uniq_subscription_entitlement_org_key",
            )
        ]


class Quota(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="quotas",
    )
    key = models.CharField(max_length=120, db_index=True)
    limit = models.BigIntegerField(default=0)
    unit = models.CharField(max_length=30, default="count")
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "subscription_quota"
        constraints = [
            models.UniqueConstraint(fields=["organization", "key"], name="uniq_subscription_quota")
        ]


class UsageCounter(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="usage_counters",
    )
    key = models.CharField(max_length=120, db_index=True)
    value = models.BigIntegerField(default=0)
    window = models.CharField(max_length=30, default="lifetime", db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "subscription_usage"
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "key", "window"],
                name="uniq_subscription_usage",
            )
        ]

