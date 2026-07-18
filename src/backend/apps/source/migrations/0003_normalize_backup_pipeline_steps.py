from django.db import migrations


def normalize_pipeline_steps(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO source_backup_pipeline (
                created_at,
                updated_at,
                is_deleted,
                deleted_at,
                organization_id,
                source_kind,
                ref_id,
                step
            )
            SELECT
                NOW(),
                NOW(),
                FALSE,
                NULL,
                n.organization_id,
                'agent',
                n.id,
                CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM protection_backup_config c
                        WHERE c.organization_id = n.organization_id
                          AND c.source_type = 'agent'
                          AND c.source_ref_id = n.id
                    )
                    THEN 3
                    ELSE 1
                END
            FROM node_nodes n
            WHERE n.role = 'agent'
              AND n.is_deleted = FALSE
            ON CONFLICT (organization_id, source_kind, ref_id)
            DO UPDATE SET
                step = GREATEST(source_backup_pipeline.step, EXCLUDED.step),
                is_deleted = FALSE,
                deleted_at = NULL,
                updated_at = NOW()
            """
        )
        cursor.execute(
            """
            INSERT INTO source_backup_pipeline (
                created_at,
                updated_at,
                is_deleted,
                deleted_at,
                organization_id,
                source_kind,
                ref_id,
                step
            )
            SELECT
                NOW(),
                NOW(),
                FALSE,
                NULL,
                s.organization_id,
                'nas',
                s.id,
                CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM protection_backup_config c
                        WHERE c.organization_id = s.organization_id
                          AND c.source_type = 'nas'
                          AND c.source_ref_id = s.id
                    )
                    THEN 3
                    ELSE 1
                END
            FROM source_resource s
            WHERE s.resource_type = 'nas'
              AND s.is_deleted = FALSE
            ON CONFLICT (organization_id, source_kind, ref_id)
            DO UPDATE SET
                step = GREATEST(source_backup_pipeline.step, EXCLUDED.step),
                is_deleted = FALSE,
                deleted_at = NULL,
                updated_at = NOW()
            """
        )


class Migration(migrations.Migration):
    dependencies = [
        ("protection", "0003_snapshot_capacity_fields"),
        ("source", "0002_source_backup_pipeline"),
    ]

    operations = [
        migrations.RunPython(normalize_pipeline_steps, migrations.RunPython.noop),
    ]
