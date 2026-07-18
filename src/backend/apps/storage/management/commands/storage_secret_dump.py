from __future__ import annotations

import json
import logging

from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError

from apps.storage.repositories.models import Credential, Repository
from apps.storage.services.internal.repository_secrets import resolve_repository_secrets

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Dump decrypted storage repository credential payload for container-side diagnostics."

    def add_arguments(self, parser):
        parser.add_argument("--org-id", type=int, dest="org_id")
        parser.add_argument("--repository-id", type=int, dest="repository_id")
        parser.add_argument("--credential-id", type=int, dest="credential_id")
        parser.add_argument("--allow-infer-org", action="store_true", dest="allow_infer_org")

    def handle(self, *args, **options):
        org_id = options.get("org_id")
        repository_id = options.get("repository_id")
        credential_id = options.get("credential_id")
        allow_infer_org = bool(options.get("allow_infer_org"))

        if not repository_id and not credential_id:
            raise CommandError("Pass --repository-id or --credential-id.")
        if not org_id:
            if allow_infer_org and repository_id:
                repository = Repository.objects.filter(id=repository_id).first()
                if repository is None:
                    raise CommandError("Repository not found.")
                org_id = repository.organization_id
            else:
                raise CommandError("--org-id is required unless --repository-id and --allow-infer-org are provided.")
        else:
            repository = None

        if repository_id:
            repository = Repository.objects.filter(id=repository_id).first()
            if repository is None:
                raise CommandError("Repository not found.")
            if int(repository.organization_id) != int(org_id):
                raise CommandError("Repository does not belong to --org-id.")
            if credential_id and int(repository.credential_id or 0) != int(credential_id):
                raise CommandError("Repository credential_id does not match --credential-id.")
            try:
                payload = resolve_repository_secrets(repository)
            except ValidationError as exc:
                raise CommandError(str(exc)) from exc
            resolved_credential_id = repository.credential_id
        else:
            credential = Credential.objects.filter(
                id=credential_id,
                organization_id=org_id,
            ).first()
            if credential is None:
                raise CommandError("Credential not found in --org-id.")
            try:
                payload = credential.get_secret_payload()
            except Exception as exc:
                raise CommandError("Credential cannot be decrypted.") from exc
            resolved_credential_id = credential.id

        logger.info(
            "storage secret dump organization_id=%s repository_id=%s credential_id=%s",
            org_id,
            repository_id,
            resolved_credential_id,
        )
        self.stdout.write(json.dumps(payload or {}, ensure_ascii=False, indent=2, sort_keys=True))
