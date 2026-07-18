"""Rename legacy ``source`` role to ``agent``; add ``proxy`` choice."""

from django.db import migrations, models


def migrate_source_to_agent(apps, schema_editor):
    Node = apps.get_model("node", "Node")
    NodeToken = apps.get_model("node", "NodeToken")
    Node.objects.filter(role="source").update(role="agent")
    NodeToken.objects.filter(role="source").update(role="agent")


class Migration(migrations.Migration):
    dependencies = [
        ("node", "0002_align_legacy_node_tables"),
    ]

    operations = [
        migrations.RunPython(migrate_source_to_agent, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="node",
            name="role",
            field=models.CharField(
                choices=[
                    ("agent", "Agent"),
                    ("proxy", "Proxy"),
                    ("gateway", "Gateway"),
                ],
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="nodetoken",
            name="role",
            field=models.CharField(
                choices=[
                    ("agent", "Agent"),
                    ("proxy", "Proxy"),
                    ("gateway", "Gateway"),
                ],
                max_length=20,
            ),
        ),
    ]
