from __future__ import annotations

_MIN_TOTAL_RATIO = 0.95
_MAX_ESTIMATE_OVER_REFERENCE = 3.0


def credible_bytes_total(*, bytes_done: int, bytes_total: int | None) -> bool:
    if bytes_total is None or int(bytes_total) <= 0:
        return False
    total = int(bytes_total)
    done = max(0, int(bytes_done or 0))
    if done <= 0:
        return True
    return total * 100 >= done * int(_MIN_TOTAL_RATIO * 100)


def apply_reference_bytes_total(
    *,
    bytes_total: int | None,
    reference_bytes_total: int | None,
) -> tuple[int | None, bool]:
    reference = max(0, int(reference_bytes_total or 0))
    if reference <= 0 or bytes_total is None or int(bytes_total) <= 0:
        return bytes_total, False
    total = int(bytes_total)
    if total > reference * _MAX_ESTIMATE_OVER_REFERENCE:
        return reference, True
    return total, False


def monotonic_bytes_total(
    *,
    bytes_done: int,
    bytes_total: int | None,
    previous_max: int | None,
    reference_bytes_total: int | None = None,
) -> int | None:
    done = max(0, int(bytes_done or 0))
    reference = max(0, int(reference_bytes_total or 0))
    adjusted, _ = apply_reference_bytes_total(
        bytes_total=bytes_total,
        reference_bytes_total=reference,
    )

    candidates: list[int] = []
    if adjusted is not None and int(adjusted) > 0 and credible_bytes_total(bytes_done=done, bytes_total=int(adjusted)):
        candidates.append(int(adjusted))
    if reference > 0 and credible_bytes_total(bytes_done=done, bytes_total=reference):
        candidates.append(reference)
    if previous_max is not None and int(previous_max) > 0 and credible_bytes_total(
        bytes_done=done,
        bytes_total=int(previous_max),
    ):
        candidates.append(int(previous_max))

    if not candidates:
        return None
    return max(done, min(candidates))
