from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def _resolve_gateway_link(gateway_links, knowledge_source):
    """Resolve the only authoritative link for one historical KS row."""

    exact = list(
        gateway_links.filter(
            organization_id=knowledge_source.organization_id,
            gateway_id=knowledge_source.gateway_id,
        ).values_list("id", flat=True)
    )
    if len(exact) == 1:
        return exact[0]

    platform = list(
        gateway_links.filter(
            gateway_id=knowledge_source.gateway_id,
            scope="platform",
        ).values_list("id", flat=True)
    )
    if len(platform) == 1:
        return platform[0]

    candidates = list(
        gateway_links.filter(
            gateway_id=knowledge_source.gateway_id,
        ).values_list("id", flat=True)
    )
    if len(candidates) == 1:
        return candidates[0]

    raise RuntimeError(
        "Cannot resolve an authoritative data gateway link for existing "
        f"knowledge source id={knowledge_source.id}; "
        f"candidate_link_ids={candidates}."
    )


def backfill_gateway_identity(apps, schema_editor):
    """Backfill KS execution links and validate existing Gateway ownership."""

    LensGatewayLink = apps.get_model("lens_bridge", "LensGatewayLink")
    LensKnowledgeSource = apps.get_model("lens_bridge", "LensKnowledgeSource")
    LensSessionLink = apps.get_model("lens_bridge", "LensSessionLink")
    database_alias = schema_editor.connection.alias

    gateway_links = LensGatewayLink.objects.using(database_alias)
    knowledge_sources = LensKnowledgeSource.objects.using(database_alias)
    session_links = LensSessionLink.objects.using(database_alias)

    for knowledge_source in knowledge_sources.filter(
        gateway_link_id__isnull=True
    ).iterator():
        link_id = _resolve_gateway_link(gateway_links, knowledge_source)
        knowledge_sources.filter(pk=knowledge_source.pk).update(
            gateway_link_id=link_id
        )

    unresolved_owner_links = []
    for link in gateway_links.filter(scope="user", owner_user_id__isnull=True).iterator():
        owner_ids = set(
            knowledge_sources.filter(
                gateway_link_id=link.id,
                created_by_id__isnull=False,
            ).values_list("created_by_id", flat=True)
        )
        owner_ids.update(
            session_links.filter(
                knowledge_source__gateway_link_id=link.id,
                hfl_user_id__isnull=False,
            ).values_list("hfl_user_id", flat=True)
        )
        if len(owner_ids) != 1:
            unresolved_owner_links.append(
                {"link_id": link.id, "candidate_owner_ids": sorted(owner_ids)}
            )
            continue
        gateway_links.filter(pk=link.pk).update(owner_user_id=owner_ids.pop())

    if unresolved_owner_links:
        raise RuntimeError(
            "Cannot determine one owner for existing private data gateway "
            f"links: {unresolved_owner_links}."
        )

    gateway_links.filter(
        scope="platform",
        owner_user_id__isnull=False,
    ).update(owner_user_id=None)


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("lens_bridge", "0020_alter_lensgatewaylink_sidecar_status"),
    ]

    operations = [
        migrations.AlterField(
            model_name="lensgatewaylink",
            name="owner_user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="lens_gateway_links_owned",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="lensknowledgesource",
            name="gateway_link",
            field=models.ForeignKey(
                null=True,
                help_text="Authoritative gateway authorization used for execution.",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="knowledge_sources",
                to="lens_bridge.lensgatewaylink",
            ),
        ),
        migrations.RunPython(
            backfill_gateway_identity,
            migrations.RunPython.noop,
        ),
    ]
