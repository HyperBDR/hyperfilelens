from django.conf import settings
from django.db import migrations, models


def backfill_assistant_links(apps, schema_editor):
    LensKnowledgeSource = apps.get_model("lens_bridge", "LensKnowledgeSource")
    LensAssistantLink = apps.get_model("lens_bridge", "LensAssistantLink")
    for ks in LensKnowledgeSource.objects.filter(sl_assistant_uuid__isnull=False).iterator():
        LensAssistantLink.objects.get_or_create(
            organization_id=ks.organization_id,
            sl_assistant_uuid=ks.sl_assistant_uuid,
            defaults={
                "knowledge_source_id": ks.id,
                "visibility_scope": "organization",
                "created_by_id": ks.created_by_id,
                "owner_user_id": None,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("lens_bridge", "0007_knowledge_source_sync_state"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LensAssistantLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="%(app_label)s_%(class)s_set",
                        to="iam.organization",
                    ),
                ),
                ("sl_assistant_uuid", models.UUIDField(db_index=True)),
                (
                    "visibility_scope",
                    models.CharField(
                        choices=[("user", "Only me"), ("organization", "Organization")],
                        db_index=True,
                        default="organization",
                        max_length=16,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="lens_assistant_links_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "knowledge_source",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="assistant_links",
                        to="lens_bridge.lensknowledgesource",
                    ),
                ),
                (
                    "owner_user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="lens_assistant_links_owned",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "lens_bridge_assistant_link",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="lensassistantlink",
            index=models.Index(fields=["organization", "visibility_scope"], name="lens_basst_org_scope_idx"),
        ),
        migrations.AddConstraint(
            model_name="lensassistantlink",
            constraint=models.UniqueConstraint(
                fields=("organization", "sl_assistant_uuid"),
                name="uniq_lens_bridge_asst_link_org_uuid",
            ),
        ),
        migrations.RunPython(backfill_assistant_links, migrations.RunPython.noop),
    ]
