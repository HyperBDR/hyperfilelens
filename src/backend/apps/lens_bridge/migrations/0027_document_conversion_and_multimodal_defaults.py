from django.db import migrations, models


def backfill_deployment_model_roles(apps, schema_editor):
    model_link = apps.get_model("lens_bridge", "LensOrgModelLink")
    managed_links = model_link.objects.exclude(management_key="")
    managed_links.update(deployment_role="agent")
    managed_links.filter(
        management_key__startswith="deployment-multimodal"
    ).update(deployment_role="multimodal")


def clear_deployment_model_roles(apps, schema_editor):
    model_link = apps.get_model("lens_bridge", "LensOrgModelLink")
    model_link.objects.update(
        deployment_role="",
        is_deployment_history=False,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("lens_bridge", "0026_lenssluserlink_sl_email"),
    ]

    operations = [
        migrations.AddField(
            model_name="lensorglink",
            name="default_multimodal_model_ref",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="lensknowledgesource",
            name="sl_datasource_uuid",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="lensknowledgesource",
            name="sync_claim_token",
            field=models.UUIDField(blank=True, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="lensknowledgesource",
            name="sync_claimed_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="lensknowledgesource",
            name="sync_next_poll_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="lensorgmodellink",
            name="deployment_role",
            field=models.CharField(
                blank=True,
                choices=[("agent", "Agent"), ("multimodal", "Multimodal")],
                db_index=True,
                default="",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="lensorgmodellink",
            name="is_deployment_history",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="lensorgmodellink",
            name="deployment_fingerprint",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.RunPython(
            backfill_deployment_model_roles,
            clear_deployment_model_roles,
        ),
        migrations.AddField(
            model_name="lenssessionlink",
            name="multimodal_model_ref",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
        migrations.AlterField(
            model_name="lenssessionlink",
            name="provision_phase",
            field=models.CharField(
                choices=[
                    ("queued", "Queued"),
                    ("restoring", "Restoring backup data"),
                    ("converting", "Extracting document content"),
                    (
                        "creating_knowledge_source",
                        "Creating knowledge source",
                    ),
                    ("creating_assistant", "Creating assistant"),
                    ("granting_assistant", "Granting assistant"),
                    ("creating_session", "Creating chat session"),
                    ("ready", "Ready"),
                    ("cleaning_up", "Cleaning up"),
                    ("deleting", "Deleting"),
                    ("deleted", "Deleted"),
                ],
                db_index=True,
                default="ready",
                max_length=32,
            ),
        ),
    ]
