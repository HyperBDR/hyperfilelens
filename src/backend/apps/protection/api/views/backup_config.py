from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.iam.org_context import require_org
from apps.iam.permissions_org import IsOrgOperator, IsOrgReader
from apps.protection.api.pagination import ProtectionPagination
from apps.protection.api.serializers import (
    BackupConfigDetailSerializer,
    BackupConfigListSerializer,
    BackupConfigResetSerializer,
    BackupConfigWriteSerializer,
)
from apps.protection.models import BackupConfig
from apps.protection.selectors.backup_config import (
    backup_configs_queryset,
    filter_backup_configs,
    get_backup_config,
)
from apps.protection import services as protection_services
from apps.protection.tasks.repository_policy import sync_backup_config_repository_policy_task


def _validation_error(exc: DjangoValidationError) -> ValidationError:
    if hasattr(exc, "message_dict"):
        return ValidationError(exc.message_dict)
    return ValidationError({"detail": exc.messages})


class BackupConfigViewSet(viewsets.ModelViewSet):
    serializer_class = BackupConfigListSerializer
    permission_classes = [IsAuthenticated, IsOrgOperator]
    pagination_class = ProtectionPagination
    queryset = BackupConfig.objects.none()

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated(), IsOrgReader()]
        return super().get_permissions()

    def get_queryset(self):
        org = require_org(self.request)
        params = self.request.query_params
        repo_id = params.get("repository_id")
        return filter_backup_configs(
            backup_configs_queryset(organization_id=org.id),
            search=params.get("search") or None,
            source_type=params.get("source_type") or None,
            repository_id=int(repo_id) if repo_id else None,
            ordering=params.get("ordering") or None,
        )

    def get_object(self):
        org = require_org(self.request)
        config = get_backup_config(organization_id=org.id, config_id=int(self.kwargs["pk"]))
        if config is None:
            raise NotFound("backup config not found")
        return config

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        org = require_org(request)
        serializer = BackupConfigWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            config = protection_services.backup_config.create_backup_config(
                organization_id=org.id,
                data=serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
        transaction.on_commit(
            lambda config_id=config.id: sync_backup_config_repository_policy_task.delay(config_id=config_id)
        )
        return Response(
            BackupConfigDetailSerializer(config).data,
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        config = self.get_object()
        return Response(BackupConfigDetailSerializer(config).data)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        config = self.get_object()
        serializer = BackupConfigWriteSerializer(data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        try:
            config = protection_services.backup_config.update_backup_config(
                config=config,
                data=serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
        transaction.on_commit(
            lambda config_id=config.id: sync_backup_config_repository_policy_task.delay(config_id=config_id)
        )
        return Response(BackupConfigDetailSerializer(config).data)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        config = self.get_object()
        try:
            result = protection_services.backup_config.delete_backup_config(config=config)
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
        return Response(result, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="reset")
    def reset(self, request, *args, **kwargs):
        org = require_org(request)
        serializer = BackupConfigResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = protection_services.backup_config_reset.create_reset_tasks_for_sources(
                organization_id=org.id,
                source_ids=serializer.validated_data["source_ids"],
                confirmation=serializer.validated_data["confirmation"],
            )
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
        return Response(result, status=status.HTTP_202_ACCEPTED)
