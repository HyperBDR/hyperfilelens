from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("iam", "0001_initial"),
        ("protection", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="InsightReport",
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
                ("report_type", models.CharField(db_index=True, default="ai_scan", max_length=50)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("running", "Running"),
                            ("ready", "Ready"),
                            ("failed", "Failed"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("summary", models.JSONField(blank=True, default=dict)),
                ("error", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="insight_reports",
                        to="iam.organization",
                    ),
                ),
                (
                    "snapshot",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="insight_reports",
                        to="protection.backupsourcesnapshotdirectory",
                    ),
                ),
            ],
            options={
                "db_table": "insight_report",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="insightreport",
            index=models.Index(
                fields=["organization", "report_type", "created_at"],
                name="insight_rep_organ_8e0d6a_idx",
            ),
        ),
        migrations.CreateModel(
            name="InsightFinding",
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
                ("finding_type", models.CharField(db_index=True, max_length=80)),
                ("severity", models.CharField(db_index=True, default="info", max_length=20)),
                ("title", models.CharField(max_length=300)),
                ("detail", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="insight_findings",
                        to="iam.organization",
                    ),
                ),
                (
                    "report",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="findings",
                        to="insight.insightreport",
                    ),
                ),
                (
                    "snapshot",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="insight_findings",
                        to="protection.backupsourcesnapshotdirectory",
                    ),
                ),
            ],
            options={
                "db_table": "insight_finding",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="insightfinding",
            index=models.Index(
                fields=["organization", "snapshot", "created_at"],
                name="insight_fin_organ_6ee5f6_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="insightfinding",
            index=models.Index(
                fields=["organization", "finding_type", "created_at"],
                name="insight_fin_organ_8fcb32_idx",
            ),
        ),
    ]
