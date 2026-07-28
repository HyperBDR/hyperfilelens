"""Platform Ops Object Storage Provider Catalog APIs."""

from __future__ import annotations

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.platform_ops.api.permissions import IsPlatformOpsStaff
from apps.platform_ops.api.serializers.storage_providers import (
    ProviderCatalogApplySerializer,
    ProviderCatalogContentSerializer,
    ProviderCatalogResetSerializer,
    ProviderValidationCredentialSerializer,
    ProviderValidationRunCreateSerializer,
)
from apps.platform_ops.models import PlatformAuditLog
from apps.platform_ops.services.internal.audit import write_platform_audit_log
from apps.storage.provider_catalog.errors import (
    ProviderCatalogConflictError,
    ProviderCatalogValidationError,
)
from apps.storage.provider_catalog.models import StorageProviderValidationRun
from apps.storage.provider_catalog.validation import (
    cancel_validation_run,
    create_validation_run,
    retry_validation_run,
    serialize_validation_run,
)
from apps.storage.selectors.interface import list_effective_storage_providers
from apps.storage.services.interface import (
    apply_provider_catalog_import,
    confirm_provider_catalog_reset,
    diff_provider_catalog_import,
    export_provider_catalog,
    review_provider_catalog_import,
    review_provider_catalog_reset,
)


class ProviderCatalogConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "provider_catalog_conflict"


def _raise_api_error(exc: Exception) -> None:
    if isinstance(exc, ProviderCatalogConflictError):
        raise ProviderCatalogConflict(
            {"detail": exc.message, "error_code": exc.code}
        ) from exc
    if isinstance(exc, ProviderCatalogValidationError):
        detail: dict = {"content": [exc.message]}
        if exc.issues:
            detail["reasons"] = exc.issues
        raise ValidationError(detail) from exc
    raise exc


def _provider_ids_from_query(request) -> list[str] | None:
    if "provider_ids" not in request.query_params:
        return None
    values: list[str] = []
    for raw in request.query_params.getlist("provider_ids"):
        values.extend(item.strip() for item in raw.split(",") if item.strip())
    return values


def _audit(
    request,
    *,
    action: str,
    provider_ids: list[str],
    details: dict | None = None,
    result: str = PlatformAuditLog.Result.SUCCESS,
) -> None:
    write_platform_audit_log(
        request=request,
        action=action,
        target_type="storage_provider_catalog",
        target_id=",".join(provider_ids),
        details={"provider_ids": provider_ids, **(details or {})},
        result=result,
    )


def _diff_summary(payload: dict) -> dict:
    providers = payload.get("providers") or []
    return {
        "input_checksum": payload.get("input_checksum"),
        "provider_count": len(providers),
        "change_types": {
            item["provider_id"]: item.get("change_type") for item in providers
        },
        "persistence_actions": {
            item["provider_id"]: item.get("persistence_action") for item in providers
        },
        "high_risk_change_count": sum(
            len(item.get("high_risk_changes") or []) for item in providers
        ),
    }


def _audit_validation_failure(request, *, action: str, run, exc: Exception) -> None:
    _audit(
        request,
        action=action,
        provider_ids=[run.provider_id],
        details={
            "run_id": str(run.id),
            "status": run.status,
            "error_code": getattr(exc, "code", None),
        },
        result=PlatformAuditLog.Result.FAILURE,
    )


class _NoStoreView(APIView):
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        response["Pragma"] = "no-cache"
        return response


class PlatformOpsStorageProvidersView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def get(self, _request):
        providers = list_effective_storage_providers()
        runs = StorageProviderValidationRun.objects.prefetch_related(
            "region_validations"
        ).order_by("provider_id")
        return Response(
            {
                "schema_version": 1,
                "providers": providers,
                "validation_runs": [serialize_validation_run(run) for run in runs],
            }
        )


class PlatformOpsStorageProviderImportDiffView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def post(self, request):
        serializer = ProviderCatalogContentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = diff_provider_catalog_import(serializer.validated_data["content"])
        except (ProviderCatalogValidationError, ProviderCatalogConflictError) as exc:
            _audit(
                request,
                action="storage_provider.import.diff",
                provider_ids=[],
                result=PlatformAuditLog.Result.FAILURE,
            )
            _raise_api_error(exc)
        _audit(
            request,
            action="storage_provider.import.diff",
            provider_ids=result["target_provider_ids"],
            details=_diff_summary(result),
        )
        return Response(result)


class PlatformOpsStorageProviderImportReviewView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def post(self, request):
        serializer = ProviderCatalogContentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = review_provider_catalog_import(
                serializer.validated_data["content"],
                user_id=request.user.pk,
            )
        except (ProviderCatalogValidationError, ProviderCatalogConflictError) as exc:
            _audit(
                request,
                action="storage_provider.import.review",
                provider_ids=[],
                result=PlatformAuditLog.Result.FAILURE,
            )
            _raise_api_error(exc)
        _audit(
            request,
            action="storage_provider.import.review",
            provider_ids=result["target_provider_ids"],
            details=_diff_summary(result),
        )
        return Response(result)


class PlatformOpsStorageProviderImportApplyView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def post(self, request):
        serializer = ProviderCatalogApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            with transaction.atomic():
                result = apply_provider_catalog_import(
                    data["content"],
                    user_id=request.user.pk,
                    input_checksum=data["input_checksum"],
                    review_token=data["review_token"],
                    risk_confirmations=data["risk_confirmations"],
                )
                if result["applied"]:
                    _audit(
                        request,
                        action="storage_provider.import.apply",
                        provider_ids=result["provider_ids"],
                        details={
                            "input_checksum": result["input_checksum"],
                            "changes": result["changes"],
                        },
                    )
        except (ProviderCatalogValidationError, ProviderCatalogConflictError) as exc:
            _audit(
                request,
                action="storage_provider.import.apply",
                provider_ids=[],
                result=PlatformAuditLog.Result.FAILURE,
            )
            _raise_api_error(exc)
        return Response(result)


class PlatformOpsStorageProviderExportView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def get(self, request):
        provider_ids = _provider_ids_from_query(request)
        try:
            catalog, content = export_provider_catalog(provider_ids)
        except (ProviderCatalogValidationError, ProviderCatalogConflictError) as exc:
            _audit(
                request,
                action="storage_provider.catalog.export",
                provider_ids=provider_ids or [],
                result=PlatformAuditLog.Result.FAILURE,
            )
            _raise_api_error(exc)
        exported_ids = [item["id"] for item in catalog["providers"]]
        _audit(
            request,
            action="storage_provider.catalog.export",
            provider_ids=exported_ids,
            details={"provider_count": len(exported_ids)},
        )
        response = HttpResponse(content, content_type="application/json; charset=utf-8")
        response["Content-Disposition"] = (
            'attachment; filename="storage-provider-catalog.json"'
        )
        response["X-Content-Type-Options"] = "nosniff"
        return response


class _ResetReviewBase(APIView):
    permission_classes = [IsPlatformOpsStaff]
    provider_scoped = False

    def post(self, request, provider_id: str | None = None):
        selected = provider_id if self.provider_scoped else None
        try:
            result = review_provider_catalog_reset(
                user_id=request.user.pk,
                provider_id=selected,
            )
        except (ProviderCatalogValidationError, ProviderCatalogConflictError) as exc:
            _audit(
                request,
                action="storage_provider.reset.review",
                provider_ids=[selected] if selected else [],
                result=PlatformAuditLog.Result.FAILURE,
            )
            _raise_api_error(exc)
        _audit(
            request,
            action="storage_provider.reset.review",
            provider_ids=result["provider_ids"],
            details={"scope": result["scope"]},
        )
        return Response(result)


class PlatformOpsStorageProviderResetReviewView(_ResetReviewBase):
    provider_scoped = True


class PlatformOpsStorageProvidersResetReviewView(_ResetReviewBase):
    provider_scoped = False


class _ResetConfirmBase(APIView):
    permission_classes = [IsPlatformOpsStaff]
    provider_scoped = False

    def post(self, request, provider_id: str | None = None):
        serializer = ProviderCatalogResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                result = confirm_provider_catalog_reset(
                    user_id=request.user.pk,
                    reset_token=serializer.validated_data["reset_token"],
                )
                scope_mismatch = (
                    self.provider_scoped and result["scope"] != "provider"
                ) or (not self.provider_scoped and result["scope"] != "all")
                provider_mismatch = self.provider_scoped and result["provider_ids"] != [
                    provider_id
                ]
                if scope_mismatch or provider_mismatch:
                    raise ProviderCatalogConflictError(
                        "Reset token does not match the requested scope."
                    )
                if result["reset"]:
                    _audit(
                        request,
                        action="storage_provider.reset",
                        provider_ids=result["provider_ids"],
                        details={
                            "deleted_provider_ids": result["deleted_provider_ids"]
                        },
                    )
        except (ProviderCatalogValidationError, ProviderCatalogConflictError) as exc:
            _audit(
                request,
                action="storage_provider.reset",
                provider_ids=[provider_id] if provider_id else [],
                result=PlatformAuditLog.Result.FAILURE,
            )
            _raise_api_error(exc)
        return Response(result)


class PlatformOpsStorageProviderResetView(_ResetConfirmBase):
    provider_scoped = True


class PlatformOpsStorageProvidersResetView(_ResetConfirmBase):
    provider_scoped = False


class PlatformOpsStorageProviderValidationRunCreateView(_NoStoreView):
    permission_classes = [IsPlatformOpsStaff]

    def post(self, request):
        serializer = ProviderValidationRunCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            run = create_validation_run(
                provider_id=data["provider_id"],
                region_ids=data["region_ids"],
                access_key_id=data["access_key_id"],
                secret_access_key=data["secret_access_key"],
                requested_by_id=request.user.pk,
                candidate_config=data["candidate_config"],
            )
        except (ProviderCatalogValidationError, ProviderCatalogConflictError) as exc:
            _audit(
                request,
                action="storage_provider.validation.create",
                provider_ids=[data.get("provider_id", "")],
                result=PlatformAuditLog.Result.FAILURE,
            )
            _raise_api_error(exc)
        _audit(
            request,
            action="storage_provider.validation.create",
            provider_ids=[run.provider_id],
            details={
                "run_id": str(run.id),
                "region_ids": data["region_ids"],
            },
        )
        return Response(serialize_validation_run(run), status=status.HTTP_202_ACCEPTED)


class PlatformOpsStorageProviderValidationRunDetailView(_NoStoreView):
    permission_classes = [IsPlatformOpsStaff]

    def get(self, _request, run_id):
        run = get_object_or_404(
            StorageProviderValidationRun.objects.prefetch_related("region_validations"),
            pk=run_id,
        )
        return Response(serialize_validation_run(run))


class _ValidationRunActionBase(_NoStoreView):
    permission_classes = [IsPlatformOpsStaff]

    def _run(self, run_id):
        return get_object_or_404(StorageProviderValidationRun, pk=run_id)


class PlatformOpsStorageProviderValidationRunCancelView(_ValidationRunActionBase):
    def post(self, request, run_id):
        run = self._run(run_id)
        try:
            run = cancel_validation_run(
                run_id=run.id,
                requested_by_id=request.user.pk,
            )
        except (ProviderCatalogValidationError, ProviderCatalogConflictError) as exc:
            _audit_validation_failure(
                request,
                action="storage_provider.validation.cancel",
                run=run,
                exc=exc,
            )
            _raise_api_error(exc)
        _audit(
            request,
            action="storage_provider.validation.cancel",
            provider_ids=[run.provider_id],
            details={"run_id": str(run.id), "status": run.status},
        )
        return Response(serialize_validation_run(run), status=status.HTTP_202_ACCEPTED)


class PlatformOpsStorageProviderValidationRunRetryView(_ValidationRunActionBase):
    def post(self, request, run_id):
        serializer = ProviderValidationCredentialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        run = self._run(run_id)
        try:
            run = retry_validation_run(
                run_id=run.id,
                requested_by_id=request.user.pk,
                **serializer.validated_data,
            )
        except (ProviderCatalogValidationError, ProviderCatalogConflictError) as exc:
            _audit_validation_failure(
                request,
                action="storage_provider.validation.retry",
                run=run,
                exc=exc,
            )
            _raise_api_error(exc)
        _audit(
            request,
            action="storage_provider.validation.retry",
            provider_ids=[run.provider_id],
            details={"run_id": str(run.id), "status": run.status},
        )
        return Response(serialize_validation_run(run), status=status.HTTP_202_ACCEPTED)
