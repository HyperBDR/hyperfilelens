from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from apps.storage.repositories.models import Repository
from apps.storage.services.internal.s3_client import endpoint_for_kopia
from apps.storage.services.internal.repository_secrets import resolve_repository_secrets


class KopiaCliError(Exception):
    pass


class KopiaRepositoryAlreadyExistsError(KopiaCliError):
    pass


@dataclass(frozen=True)
class KopiaResult:
    stdout: str
    stderr: str


def create_s3_repository(repository: Repository, *, timeout_seconds: int | None = None) -> KopiaResult:
    result = _run_repository_command(
        repository,
        ["repository", "create", "s3", *_s3_flags(repository)],
        timeout_seconds=timeout_seconds,
    )
    if result.returncode == 0:
        return KopiaResult(stdout=result.stdout, stderr=result.stderr)

    if _repository_already_exists(result):
        raise KopiaRepositoryAlreadyExistsError(
            _format_failure("Kopia S3 repository already exists", result)
        )

    raise KopiaCliError(_format_failure("Kopia S3 repository create failed", result))


def connect_s3_repository(repository: Repository, *, timeout_seconds: int | None = None) -> KopiaResult:
    result = _run_repository_command(
        repository,
        ["repository", "connect", "s3", *_s3_flags(repository)],
        timeout_seconds=timeout_seconds,
    )
    if result.returncode != 0:
        raise KopiaCliError(_format_failure("Kopia S3 repository connect failed", result))
    return KopiaResult(stdout=result.stdout, stderr=result.stderr)


def status(repository: Repository, *, timeout_seconds: int | None = None) -> KopiaResult:
    result = _run_repository_command(
        repository,
        ["repository", "status"],
        timeout_seconds=timeout_seconds,
    )
    if result.returncode != 0:
        raise KopiaCliError(_format_failure("Kopia repository status failed", result))
    return KopiaResult(stdout=result.stdout, stderr=result.stderr)


def content_stats(repository: Repository, *, timeout_seconds: int | None = None) -> KopiaResult:
    result = _run_repository_command(
        repository,
        ["content", "stats", "--json"],
        timeout_seconds=timeout_seconds,
    )
    if result.returncode != 0 and "unknown long flag '--json'" in f"{result.stdout}\n{result.stderr}":
        result = _run_repository_command(
            repository,
            ["content", "stats"],
            timeout_seconds=timeout_seconds,
        )
    if result.returncode != 0:
        raise KopiaCliError(_format_failure("Kopia content stats failed", result))
    return KopiaResult(stdout=result.stdout, stderr=result.stderr)


def run_maintenance(
    repository: Repository,
    *,
    full: bool,
    owner_identity: str,
    timeout_seconds: int | None = None,
) -> KopiaResult:
    config_file = _maintenance_config_file(repository)
    _connect_maintenance_repository(
        repository,
        timeout_seconds=timeout_seconds,
        config_file=config_file,
    )
    username, hostname = _owner_parts(owner_identity)
    client = _run_repository_command(
        repository,
        ["repository", "set-client", f"--username={username}", f"--hostname={hostname}"],
        timeout_seconds=timeout_seconds,
        config_file=config_file,
    )
    if client.returncode != 0:
        raise KopiaCliError(_format_failure("Kopia maintenance client configuration failed", client))
    configured = _run_repository_command(
        repository,
        ["maintenance", "set", f"--owner={owner_identity}", "--enable-quick=false", "--enable-full=false"],
        timeout_seconds=timeout_seconds,
        config_file=config_file,
    )
    if configured.returncode != 0:
        raise KopiaCliError(_format_failure("Kopia maintenance owner configuration failed", configured))
    args = ["maintenance", "run"]
    if full:
        args.append("--full")
    result = _run_repository_command(
        repository,
        args,
        timeout_seconds=timeout_seconds,
        config_file=config_file,
    )
    if result.returncode != 0:
        raise KopiaCliError(_format_failure("Kopia repository maintenance failed", result))
    return KopiaResult(stdout=result.stdout, stderr=result.stderr)


def _connect_maintenance_repository(
    repository: Repository,
    *,
    timeout_seconds: int | None,
    config_file: Path,
) -> None:
    last_result: subprocess.CompletedProcess[str] | None = None
    for attempt in range(3):
        last_result = _run_repository_command(
            repository,
            ["repository", "connect", "s3", *_s3_flags(repository)],
            timeout_seconds=timeout_seconds,
            config_file=config_file,
        )
        if last_result.returncode == 0:
            return
        # A previous connect may have written a usable config before reporting
        # an error. Preserve that behavior before retrying a fresh connection.
        status_result = _run_repository_command(
            repository,
            ["repository", "status"],
            timeout_seconds=timeout_seconds,
            config_file=config_file,
        )
        if status_result.returncode == 0:
            return
        if attempt < 2:
            time.sleep(2**attempt)
    assert last_result is not None
    raise KopiaCliError(_format_failure("Kopia maintenance repository connect failed", last_result))


def _owner_parts(owner_identity: str) -> tuple[str, str]:
    parts = str(owner_identity or "").strip().split("@", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise KopiaCliError("Invalid repository owner identity")
    return parts[0], parts[1]


def _run_repository_command(
    repository: Repository,
    args: list[str],
    *,
    timeout_seconds: int | None,
    config_file: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    kopia_path = _kopia_path()
    config_file = config_file or _config_file(repository)
    env = _environment(repository)
    timeout = timeout_seconds or int(os.environ.get("HFL_KOPIA_TIMEOUT_SECONDS", "120"))
    command = [
        kopia_path,
        f"--config-file={config_file}",
        "--no-persist-credentials",
        "--no-progress",
        *args,
    ]
    try:
        return subprocess.run(
            command,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise KopiaCliError(f"Kopia CLI timed out after {timeout} seconds") from exc
    except OSError as exc:
        raise KopiaCliError(f"Kopia CLI failed to start: {exc}") from exc


def _s3_flags(repository: Repository) -> list[str]:
    config = repository.config or {}
    flags = [f"--bucket={repository.s3_bucket}"]
    endpoint = endpoint_for_kopia(str(config.get("endpoint") or ""))
    if endpoint:
        flags.append(f"--endpoint={endpoint}")
    region = str(config.get("region") or "").strip()
    if not region and str(config.get("endpoint") or "").strip():
        # Match the boto3 path used by repository health checks. Supplying a
        # region also prevents Kopia from issuing a GetBucketLocation request,
        # which is unreliable on some S3-compatible gateways such as MinIO.
        region = "us-east-1"
    if region:
        flags.append(f"--region={region}")
    prefix = str(config.get("prefix") or "").strip()
    if prefix:
        flags.append(f"--prefix={prefix}")
    if config.get("use_tls") is False:
        flags.append("--disable-tls")
    # Kopia 0.22.3 does not expose a URL-style flag; S3-compatible endpoints
    # decide path-style behavior internally. Keep config.s3_url_style for S3 API checks.
    return flags


def _kopia_path() -> str:
    configured = os.environ.get("HFL_KOPIA_PATH")
    if configured:
        return configured
    found = shutil.which("kopia")
    if found:
        return found
    raise KopiaCliError("Kopia CLI not found. Set HFL_KOPIA_PATH or install kopia in PATH.")


def _config_file(repository: Repository) -> Path:
    base_dir = Path(os.environ.get("HFL_KOPIA_CONFIG_DIR", "/tmp/hfl-kopia"))
    repo_dir = base_dir / str(repository.id)
    repo_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    return repo_dir / "repository.config"


def _maintenance_config_file(repository: Repository) -> Path:
    return _config_file(repository).with_name("maintenance.repository.config")


def _environment(repository: Repository) -> dict[str, str]:
    config = repository.config or {}
    secrets_payload = resolve_repository_secrets(repository)
    env = os.environ.copy()
    env["AWS_ACCESS_KEY_ID"] = str(config.get("access_key_id") or "")
    env["AWS_SECRET_ACCESS_KEY"] = str(secrets_payload.get("secret_access_key") or "")
    region = str(config.get("region") or "").strip()
    if region:
        env["AWS_REGION"] = region
        env["AWS_DEFAULT_REGION"] = region
    env["KOPIA_PASSWORD"] = str(secrets_payload.get("kopia_password") or "")
    env["KOPIA_CHECK_FOR_UPDATES"] = "false"
    env["KOPIA_USE_KEYRING"] = "false"
    env["KOPIA_PERSIST_CREDENTIALS_ON_CONNECT"] = "false"
    return env


def _format_failure(message: str, result: subprocess.CompletedProcess[str]) -> str:
    output = "\n".join(part for part in [result.stdout, result.stderr] if part).strip()
    if not output:
        return f"{message}: exit code {result.returncode}"
    return f"{message}: exit code {result.returncode}: {output[-1200:]}"


def _repository_already_exists(result: subprocess.CompletedProcess[str]) -> bool:
    output = f"{result.stdout}\n{result.stderr}".lower()
    return any(
        token in output
        for token in ("already exists", "already initialized", "repository exists")
    )
