from __future__ import annotations

import uuid
from urllib.parse import urlparse, urlunparse

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError


DEFAULT_S3_ENDPOINT = "https://s3.amazonaws.com"


class S3ClientError(Exception):
    pass


def endpoint_for_requests(endpoint: str | None, *, use_tls: bool = True) -> str:
    raw = (endpoint or DEFAULT_S3_ENDPOINT).strip()
    if not raw:
        raw = DEFAULT_S3_ENDPOINT
    if "://" not in raw:
        raw = f"{'https' if use_tls else 'http'}://{raw}"
    parsed = urlparse(raw)
    scheme = parsed.scheme or ("https" if use_tls else "http")
    netloc = parsed.netloc or parsed.path
    path = parsed.path if parsed.netloc else ""
    return urlunparse((scheme, netloc.rstrip("/"), path.rstrip("/"), "", "", ""))


def endpoint_for_kopia(endpoint: str | None) -> str:
    raw = (endpoint or DEFAULT_S3_ENDPOINT).strip()
    if "://" in raw:
        parsed = urlparse(raw)
        return parsed.netloc or parsed.path.strip("/")
    return raw.strip("/")


def list_s3_buckets(
    *,
    endpoint: str | None,
    region: str | None,
    access_key_id: str,
    secret_access_key: str,
    s3_url_style: str | None = None,
    use_tls: bool = True,
    timeout_seconds: float = 15,
) -> list[str]:
    client = _client(
        endpoint=endpoint,
        region=region,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        s3_url_style=s3_url_style,
        use_tls=use_tls,
        timeout_seconds=timeout_seconds,
    )
    try:
        response = client.list_buckets()
    except (BotoCoreError, ClientError) as exc:
        raise S3ClientError(_error_message("Unable to list S3 buckets", exc)) from exc
    return [
        str(bucket.get("Name") or "")
        for bucket in response.get("Buckets", [])
        if bucket.get("Name")
    ]


def ensure_s3_bucket(
    *,
    endpoint: str | None,
    region: str | None,
    bucket: str,
    access_key_id: str,
    secret_access_key: str,
    s3_url_style: str | None = None,
    use_tls: bool = True,
    timeout_seconds: float = 15,
) -> None:
    client = _client(
        endpoint=endpoint,
        region=region,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        s3_url_style=s3_url_style,
        use_tls=use_tls,
        timeout_seconds=timeout_seconds,
    )
    try:
        response = client.list_buckets()
    except (BotoCoreError, ClientError) as exc:
        raise S3ClientError(_error_message("Unable to list S3 buckets", exc)) from exc

    existing_names = {
        str(bucket_info.get("Name") or "")
        for bucket_info in response.get("Buckets", [])
        if bucket_info.get("Name")
    }
    if bucket in existing_names:
        return

    try:
        create_args = {"Bucket": bucket}
        create_bucket_configuration = _create_bucket_configuration(region)
        if create_bucket_configuration:
            create_args["CreateBucketConfiguration"] = create_bucket_configuration
        client.create_bucket(**create_args)
    except ClientError as exc:
        if _client_error_code(exc) in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
            return
        raise S3ClientError(_error_message(f"Unable to create S3 bucket {bucket}", exc)) from exc
    except BotoCoreError as exc:
        raise S3ClientError(_error_message(f"Unable to create S3 bucket {bucket}", exc)) from exc


def check_s3_bucket_readable(
    *,
    endpoint: str | None,
    region: str | None,
    bucket: str,
    access_key_id: str,
    secret_access_key: str,
    s3_url_style: str | None = None,
    use_tls: bool = True,
    timeout_seconds: float = 15,
) -> None:
    """Check an existing S3 bucket without creating or modifying objects."""
    if not str(bucket or "").strip():
        raise S3ClientError("Bucket name is required.")
    client = _client(
        endpoint=endpoint,
        region=region,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        s3_url_style=s3_url_style,
        use_tls=use_tls,
        timeout_seconds=timeout_seconds,
    )
    try:
        client.head_bucket(Bucket=bucket)
    except (BotoCoreError, ClientError) as exc:
        raise S3ClientError(
            _error_message(f"Unable to access bucket {bucket}", exc)
        ) from exc


def verify_s3_bucket_rw(
    *,
    endpoint: str | None,
    region: str | None,
    bucket: str,
    access_key_id: str,
    secret_access_key: str,
    s3_url_style: str | None = None,
    use_tls: bool = True,
    timeout_seconds: float = 15,
) -> dict:
    """Verify that the given bucket is readable and writable by performing
    head_bucket + put_object + delete_object using a probe key under
    ``.hfl-verify/<uuid>.tmp``.

    Returns a dict with ``bucket``, ``probe_key``, ``wrote`` and ``deleted`` on
    success. Raises :class:`S3ClientError` on any failure.
    """
    if not str(bucket or "").strip():
        raise S3ClientError("Bucket name is required for verification.")
    client = _client(
        endpoint=endpoint,
        region=region,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        s3_url_style=s3_url_style,
        use_tls=use_tls,
        timeout_seconds=timeout_seconds,
    )
    probe_key = f".hfl-verify/{uuid.uuid4().hex}.tmp"
    body = b"hyperfilelens-verify"
    try:
        try:
            client.head_bucket(Bucket=bucket)
        except (BotoCoreError, ClientError) as exc:
            raise S3ClientError(_error_message(f"Unable to access bucket {bucket}", exc)) from exc
        try:
            client.put_object(Bucket=bucket, Key=probe_key, Body=body, ContentLength=len(body))
        except (BotoCoreError, ClientError) as exc:
            raise S3ClientError(_error_message(f"Unable to write to bucket {bucket}", exc)) from exc
        try:
            client.delete_object(Bucket=bucket, Key=probe_key)
        except (BotoCoreError, ClientError) as exc:
            raise S3ClientError(_error_message(f"Unable to clean up probe object in {bucket}", exc)) from exc
    except S3ClientError:
        # best-effort cleanup; ignore failures
        try:
            client.delete_object(Bucket=bucket, Key=probe_key)
        except Exception:
            pass
        raise
    return {"bucket": bucket, "probe_key": probe_key, "wrote": True, "deleted": True}


def delete_s3_prefix(
    *,
    endpoint: str | None,
    region: str | None,
    bucket: str,
    prefix: str,
    access_key_id: str,
    secret_access_key: str,
    s3_url_style: str | None = None,
    use_tls: bool = True,
    timeout_seconds: float = 30,
) -> dict[str, int | str]:
    """Delete one managed repository prefix without deleting its bucket."""

    normalized_prefix = str(prefix or "").strip().replace("\\", "/").strip("/")
    if not normalized_prefix:
        raise S3ClientError("Repository object prefix is required for cleanup.")
    normalized_prefix += "/"
    client = _client(
        endpoint=endpoint,
        region=region,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        s3_url_style=s3_url_style,
        use_tls=use_tls,
        timeout_seconds=timeout_seconds,
    )
    deleted_objects = 0
    deleted_versions = 0
    deleted_markers = 0
    aborted_uploads = 0
    try:
        upload_paginator = client.get_paginator("list_multipart_uploads")
        for page in upload_paginator.paginate(Bucket=bucket, Prefix=normalized_prefix):
            for upload in page.get("Uploads", []):
                key = str(upload.get("Key") or "")
                upload_id = str(upload.get("UploadId") or "")
                if not key or not upload_id:
                    continue
                client.abort_multipart_upload(Bucket=bucket, Key=key, UploadId=upload_id)
                aborted_uploads += 1

        try:
            version_paginator = client.get_paginator("list_object_versions")
            for page in version_paginator.paginate(Bucket=bucket, Prefix=normalized_prefix):
                version_entries = [
                    {"Key": item["Key"], "VersionId": item["VersionId"]}
                    for item in page.get("Versions", [])
                    if item.get("Key") and item.get("VersionId")
                ]
                marker_entries = [
                    {"Key": item["Key"], "VersionId": item["VersionId"]}
                    for item in page.get("DeleteMarkers", [])
                    if item.get("Key") and item.get("VersionId")
                ]
                for batch in _chunks(version_entries + marker_entries, 1000):
                    _delete_s3_entries(client=client, bucket=bucket, entries=batch)
                deleted_versions += len(version_entries)
                deleted_markers += len(marker_entries)
        except ClientError as exc:
            if not _is_unsupported_s3_header_error(exc):
                raise

        object_paginator = client.get_paginator("list_objects_v2")
        for page in object_paginator.paginate(Bucket=bucket, Prefix=normalized_prefix):
            entries = [
                {"Key": item["Key"]}
                for item in page.get("Contents", [])
                if item.get("Key")
            ]
            for batch in _chunks(entries, 1000):
                _delete_s3_entries(client=client, bucket=bucket, entries=batch)
            deleted_objects += len(entries)

        _verify_s3_prefix_empty(client=client, bucket=bucket, prefix=normalized_prefix)
    except (BotoCoreError, ClientError) as exc:
        raise S3ClientError(_error_message(f"Unable to delete repository prefix {normalized_prefix}", exc)) from exc
    return {
        "bucket": bucket,
        "prefix": normalized_prefix,
        "deleted_objects": deleted_objects,
        "deleted_versions": deleted_versions,
        "deleted_markers": deleted_markers,
        "aborted_uploads": aborted_uploads,
    }


def _chunks(items: list[dict], size: int):
    for offset in range(0, len(items), size):
        yield items[offset : offset + size]


def _delete_s3_entries(*, client, bucket: str, entries: list[dict]) -> None:
    try:
        response = client.delete_objects(
            Bucket=bucket,
            Delete={"Objects": entries, "Quiet": True},
        )
    except ClientError as exc:
        if not _should_fallback_from_batch_delete(exc):
            raise
        for entry in entries:
            client.delete_object(Bucket=bucket, **entry)
        return
    errors = response.get("Errors") if isinstance(response, dict) else None
    if errors:
        first = errors[0] if isinstance(errors[0], dict) else {}
        code = str(first.get("Code") or "DeleteFailed")
        message = str(first.get("Message") or "S3 rejected one or more object deletions.")
        raise S3ClientError(f"Unable to delete repository objects: {code}: {message}")


def _is_unsupported_s3_header_error(exc: ClientError) -> bool:
    if _client_error_code(exc) != "NotImplemented":
        return False
    message = str(exc.response.get("Error", {}).get("Message") or "").lower()
    return "header you provided implies functionality" in message


def _should_fallback_from_batch_delete(exc: ClientError) -> bool:
    return _is_unsupported_s3_header_error(exc) or _client_error_code(exc) == "MissingContentMD5"


def _verify_s3_prefix_empty(*, client, bucket: str, prefix: str) -> None:
    try:
        versions = client.list_object_versions(Bucket=bucket, Prefix=prefix, MaxKeys=1)
        if versions.get("Versions") or versions.get("DeleteMarkers"):
            raise S3ClientError("Repository object prefix still contains object versions after cleanup.")
    except ClientError as exc:
        if not _is_unsupported_s3_header_error(exc):
            raise
    objects = client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=1)
    if objects.get("Contents"):
        raise S3ClientError("Repository object prefix still contains objects after cleanup.")
    uploads = client.list_multipart_uploads(Bucket=bucket, Prefix=prefix, MaxUploads=1)
    if uploads.get("Uploads"):
        raise S3ClientError("Repository object prefix still contains multipart uploads after cleanup.")


def _client(
    *,
    endpoint: str | None,
    region: str | None,
    access_key_id: str,
    secret_access_key: str,
    s3_url_style: str | None,
    use_tls: bool,
    timeout_seconds: float,
):
    endpoint_url = endpoint_for_requests(endpoint, use_tls=use_tls)
    normalized_region = (region or "").strip() or "us-east-1"
    address_style = "path" if s3_url_style == "path" else "virtual"
    config = Config(
        signature_version="s3v4",
        connect_timeout=timeout_seconds,
        read_timeout=timeout_seconds,
        retries={"max_attempts": 1},
        s3={"addressing_style": address_style},
        # Some S3-compatible endpoints reject botocore's optional checksum
        # headers on multi-object deletion. Keep checksums for operations whose
        # protocol requires them, without sending optional SDK checksum headers.
        request_checksum_calculation="when_required",
        response_checksum_validation="when_required",
    )
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=normalized_region,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        use_ssl=endpoint_url.startswith("https://"),
        verify=endpoint_url.startswith("https://"),
        config=config,
    )


def _create_bucket_configuration(region: str | None) -> dict[str, str] | None:
    normalized = (region or "").strip()
    if not normalized or normalized == "us-east-1":
        return None
    return {"LocationConstraint": normalized}


def _client_error_code(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Code") or "")


def _error_message(prefix: str, exc: Exception) -> str:
    if isinstance(exc, ClientError):
        error = exc.response.get("Error", {})
        code = str(error.get("Code") or "")
        message = str(error.get("Message") or "")
        suffix = ": ".join(part for part in [code, message] if part)
        if suffix:
            return f"{prefix}: {suffix}"
    return f"{prefix}: {exc}"
