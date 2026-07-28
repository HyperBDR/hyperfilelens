import ipaddress

from django.db import migrations, models


def _usable_address(raw):
    try:
        address = ipaddress.ip_address(str(raw or "").strip())
    except ValueError:
        return None
    if (
        address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_unspecified
    ):
        return None
    return address.compressed


def split_host_and_connection_addresses(apps, _schema_editor):
    Node = apps.get_model("node", "Node")
    for node in Node.objects.all().iterator():
        old_connection_address = node.ip_address
        metadata = node.metadata if isinstance(node.metadata, dict) else {}
        inventory = metadata.get("inventory")
        inventory = inventory if isinstance(inventory, dict) else {}
        primary_address = _usable_address(inventory.get("primary_ip_address"))
        node.connection_ip_address = old_connection_address
        node.ip_address = primary_address
        node.save(update_fields=["connection_ip_address", "ip_address"])


def restore_legacy_address_semantics(apps, _schema_editor):
    Node = apps.get_model("node", "Node")
    for node in Node.objects.all().iterator():
        node.ip_address = node.connection_ip_address or node.ip_address
        node.save(update_fields=["ip_address"])


class Migration(migrations.Migration):
    dependencies = [
        ("node", "0005_nodetoken_gateway_owner"),
    ]

    operations = [
        migrations.AlterField(
            model_name="node",
            name="ip_address",
            field=models.GenericIPAddressField(
                blank=True,
                help_text="Agent-reported primary host address.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="node",
            name="connection_ip_address",
            field=models.GenericIPAddressField(
                blank=True,
                help_text="Latest HTTP/WebSocket source address observed by the control plane.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="node",
            name="network_inventory",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Bounded current Agent network-interface snapshot.",
            ),
        ),
        migrations.RunPython(
            split_host_and_connection_addresses,
            restore_legacy_address_semantics,
        ),
    ]
