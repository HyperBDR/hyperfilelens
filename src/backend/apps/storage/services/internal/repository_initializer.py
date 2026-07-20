from __future__ import annotations

from apps.storage.repositories.models import Repository
from apps.storage.services.internal.kopia_cli import (
    KopiaCliError,
    KopiaRepositoryAlreadyExistsError,
    connect_s3_repository,
    create_s3_repository,
    status as kopia_status,
)
from apps.storage.services.internal.repository_errors import (
    RepositoryAlreadyExistsError,
)
from apps.storage.services.internal.s3_client import (
    S3ClientError,
    check_s3_bucket_readable,
    ensure_s3_bucket,
    list_s3_buckets,
    verify_s3_bucket_rw,
)
from apps.storage.services.internal.repository_secrets import (
    resolve_repository_secrets,
    scrub_secrets,
    secret_values_for_scrub,
)


class RepositoryInitializationError(Exception):
    pass


def initialize_s3_repository(repository: Repository) -> None:
    config = repository.config or {}
    secrets_payload = resolve_repository_secrets(repository)
    try:
        ensure_s3_bucket(
            endpoint=str(config.get("endpoint") or ""),
            region=str(config.get("region") or ""),
            bucket=str(repository.s3_bucket or ""),
            access_key_id=str(config.get("access_key_id") or ""),
            secret_access_key=str(secrets_payload.get("secret_access_key") or ""),
            s3_url_style=str(config.get("s3_url_style") or "virtual_hosted"),
            use_tls=config.get("use_tls") is not False,
        )
        create_s3_repository(repository)
    except KopiaRepositoryAlreadyExistsError as exc:
        raise RepositoryAlreadyExistsError(_sanitize(str(exc), repository)) from exc
    except (S3ClientError, KopiaCliError) as exc:
        raise RepositoryInitializationError(_sanitize(str(exc), repository)) from exc


def validate_s3_connection(
    *,
    endpoint: str | None,
    region: str | None,
    access_key_id: str,
    secret_access_key: str,
    s3_url_style: str | None = None,
    use_tls: bool = True,
) -> list[str]:
    try:
        return list_s3_buckets(
            endpoint=endpoint,
            region=region,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            s3_url_style=s3_url_style,
            use_tls=use_tls,
        )
    except S3ClientError as exc:
        raise RepositoryInitializationError(_sanitize(str(exc), {
            "access_key_id": access_key_id,
            "secret_access_key": secret_access_key,
        })) from exc


def verify_s3_bucket_access(
    *,
    endpoint: str | None,
    region: str | None,
    bucket: str,
    access_key_id: str,
    secret_access_key: str,
    s3_url_style: str | None = None,
    use_tls: bool = True,
) -> dict:
    try:
        return verify_s3_bucket_rw(
            endpoint=endpoint,
            region=region,
            bucket=bucket,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            s3_url_style=s3_url_style,
            use_tls=use_tls,
        )
    except S3ClientError as exc:
        raise RepositoryInitializationError(_sanitize(str(exc), {
            "access_key_id": access_key_id,
            "secret_access_key": secret_access_key,
        })) from exc


def check_s3_repository(repository: Repository) -> None:
    config = repository.config or {}
    secrets_payload = resolve_repository_secrets(repository)
    try:
        check_s3_bucket_readable(
            endpoint=str(config.get("endpoint") or ""),
            region=str(config.get("region") or ""),
            bucket=str(repository.s3_bucket or ""),
            access_key_id=str(config.get("access_key_id") or ""),
            secret_access_key=str(secrets_payload.get("secret_access_key") or ""),
            s3_url_style=str(config.get("s3_url_style") or "virtual_hosted"),
            use_tls=config.get("use_tls") is not False,
        )
        connect_s3_repository(repository)
        kopia_status(repository)
    except (S3ClientError, KopiaCliError) as exc:
        raise RepositoryInitializationError(_sanitize(str(exc), repository)) from exc


def _sanitize(message: str, source) -> str:
    if isinstance(source, Repository):
        config = source.config or {}
        try:
            secrets_payload = resolve_repository_secrets(source)
        except Exception:
            secrets_payload = {}
    else:
        config = source or {}
        secrets_payload = config
    return str(scrub_secrets(message, extra_values=secret_values_for_scrub(None, secrets_payload) + [
        str(config.get("access_key_id") or "")
    ]))
