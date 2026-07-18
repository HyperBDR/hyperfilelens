"""Knowledge source ingest / document conversion policy helpers."""

from __future__ import annotations

from typing import Any

from apps.iam.models import Organization
from apps.lens_bridge.services import provisioning


DEFAULT_INGEST_POLICY: dict[str, Any] = {
    "document": False,
    "embedded_image": False,
    "image": False,
    "document_model_ref": None,
    "vision_model_ref": None,
    "max_images": 100,
    "max_file_size_mb": 100,
    "max_pages": 500,
    "pdf_extract_images": True,
    "pdf_extract_images_on_text_pages": False,
    "pdf_render_scanned_pages": False,
    "pdf_max_pages": 30,
    "pdf_max_images_per_page": 3,
    "pdf_render_dpi": 144,
    "pdf_min_text_chars": 30,
    "pdf_min_image_area_ratio": 0.08,
}

_BOOL_KEYS = (
    "document",
    "image",
    "embedded_image",
    "pdf_extract_images",
    "pdf_extract_images_on_text_pages",
    "pdf_render_scanned_pages",
)
_INT_KEYS = (
    "max_images",
    "max_file_size_mb",
    "max_pages",
    "pdf_max_images_per_page",
    "pdf_max_pages",
    "pdf_min_text_chars",
    "pdf_render_dpi",
)
_STR_KEYS = ("vision_model_ref", "document_model_ref")


def _positive_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def _ratio(value: Any, fallback: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    if parsed <= 0 or parsed > 1:
        return fallback
    return parsed


def normalize_ingest_policy(raw: dict[str, Any] | None, org: Organization | None = None) -> dict[str, Any]:
    data = dict(DEFAULT_INGEST_POLICY)
    if isinstance(raw, dict):
        for key in _BOOL_KEYS:
            if key in raw:
                data[key] = bool(raw[key])
        for key in _INT_KEYS:
            if key in raw:
                data[key] = _positive_int(raw[key], int(DEFAULT_INGEST_POLICY[key]))
        if "pdf_min_image_area_ratio" in raw:
            data["pdf_min_image_area_ratio"] = _ratio(
                raw["pdf_min_image_area_ratio"],
                float(DEFAULT_INGEST_POLICY["pdf_min_image_area_ratio"]),
            )
        for key in _STR_KEYS:
            if key in raw:
                value = raw[key]
                data[key] = str(value).strip() or None if value else None

    if data.get("embedded_image") and not data.get("document"):
        data["embedded_image"] = False

    if org is not None:
        default_model = provisioning.default_model_ref_for_org(org)
        if data.get("document") and not data.get("document_model_ref") and default_model:
            data["document_model_ref"] = default_model
        if data.get("image") and not data.get("vision_model_ref") and default_model:
            data["vision_model_ref"] = default_model

    return data


def conversion_payload_for_sl(policy: dict[str, Any]) -> dict[str, Any]:
    """Shape aligned with SourceLens sync_policy.conversion / settings.ingestion.conversion."""
    payload: dict[str, Any] = {}
    for key in _BOOL_KEYS:
        payload[key] = bool(policy.get(key))
    for key in _INT_KEYS:
        payload[key] = _positive_int(policy.get(key), int(DEFAULT_INGEST_POLICY[key]))
    payload["pdf_min_image_area_ratio"] = _ratio(
        policy.get("pdf_min_image_area_ratio"),
        float(DEFAULT_INGEST_POLICY["pdf_min_image_area_ratio"]),
    )
    if policy.get("document_model_ref"):
        payload["document_model_ref"] = str(policy["document_model_ref"])
    if policy.get("vision_model_ref"):
        payload["vision_model_ref"] = str(policy["vision_model_ref"])
    return payload


def ingest_summary(policy: dict[str, Any]) -> str:
    parts: list[str] = []
    if policy.get("document"):
        parts.append("documents")
    if policy.get("image"):
        parts.append("images")
    if policy.get("embedded_image"):
        parts.append("embedded-images")
    return "+".join(parts) if parts else "text-only"
