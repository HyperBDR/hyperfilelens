from __future__ import annotations

from django.db import models


class BackupSourceRepositoryPurgePending(models.Model):
    """Queued Kopia snapshot cleanup when strict delete cannot reach the repository."""

    organization_id = models.BigIntegerField(db_index=True)
    source_kind = models.CharField(max_length=16, db_index=True)
    source_ref_id = models.BigIntegerField(db_index=True)
    repository_id = models.BigIntegerField(db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "source_repository_purge_pending"
        indexes = [
            models.Index(
                fields=["organization_id", "repository_id", "created_at"],
                name="src_repo_purge_org_repo_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.source_kind}:{self.source_ref_id} repo={self.repository_id}"
