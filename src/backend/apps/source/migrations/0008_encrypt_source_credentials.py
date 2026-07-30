from django.db import migrations


def encrypt_source_credentials(apps, schema_editor):
    from apps.source.services.internal.source_credentials import (
        protect_source_credentials,
        scrub_source_secrets,
    )

    SourceResource = apps.get_model("source", "SourceResource")
    for resource in SourceResource.objects.all().iterator(chunk_size=500):
        protected = protect_source_credentials(resource.credentials)
        scrubbed_config = scrub_source_secrets(resource.config)
        updates = {}
        if protected != resource.credentials:
            updates["credentials"] = protected
        if scrubbed_config != resource.config:
            updates["config"] = scrubbed_config
        if updates:
            SourceResource.objects.filter(pk=resource.pk).update(**updates)


class Migration(migrations.Migration):
    dependencies = [("source", "0007_source_resource_connection_probe")]

    operations = [migrations.RunPython(encrypt_source_credentials, migrations.RunPython.noop)]
