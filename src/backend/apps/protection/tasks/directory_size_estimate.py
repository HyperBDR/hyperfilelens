from celery import shared_task

from apps.protection.services.directory_size_estimate import (
    refresh_backup_config_directory_estimates_by_id,
)

_REQUEUE_COUNTDOWN_SECONDS = 5


@shared_task(
    name="apps.protection.tasks.directory_size_estimate.refresh_backup_config_directory_estimates",
    soft_time_limit=360,
    time_limit=420,
)
def refresh_backup_config_directory_estimates_task(
    *,
    config_id: int,
    attempt: int = 1,
) -> dict:
    result = refresh_backup_config_directory_estimates_by_id(
        config_id=int(config_id),
        attempt=int(attempt or 1),
    )
    if result.get("should_requeue"):
        next_attempt = int(result.get("attempt") or 1) + 1
        refresh_backup_config_directory_estimates_task.apply_async(
            kwargs={"config_id": int(config_id), "attempt": next_attempt},
            countdown=_REQUEUE_COUNTDOWN_SECONDS,
        )
    return result
