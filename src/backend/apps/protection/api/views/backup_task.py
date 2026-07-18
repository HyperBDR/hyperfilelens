from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.iam.org_context import require_org
from apps.iam.permissions_org import IsOrgOperator
from apps.protection.api.serializers.backup_task import (
    RetryBackupDirectorySerializer,
    StartBackupTaskSerializer,
)
from apps.protection.services.backup_orchestrator import cancel_backup, retry_backup_directory
from apps.protection.services.backup_task import start_backup_tasks


def _validation_error(exc: DjangoValidationError) -> ValidationError:
    if hasattr(exc, "message_dict"):
        return ValidationError(exc.message_dict)
    return ValidationError({"detail": exc.messages})


class BackupTaskStartView(APIView):
    permission_classes = [IsAuthenticated, IsOrgOperator]

    def post(self, request):
        org = require_org(request)
        serializer = StartBackupTaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = start_backup_tasks(
                organization_id=org.id,
                sources=serializer.validated_data.get("sources"),
                source_ids=serializer.validated_data.get("source_ids"),
                backup_config_ids=serializer.validated_data.get("backup_config_ids"),
                trigger_type=serializer.validated_data.get("trigger_type") or "manual",
                idempotency_key=serializer.validated_data.get("idempotency_key"),
            )
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
        return Response(result, status=status.HTTP_201_CREATED)


class BackupTaskCancelView(APIView):
    permission_classes = [IsAuthenticated, IsOrgOperator]

    def post(self, request, task_uuid: str):
        org = require_org(request)
        try:
            result = cancel_backup(organization_id=org.id, task_uuid=str(task_uuid))
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
        return Response(result)


class BackupTaskRetryDirectoryView(APIView):
    permission_classes = [IsAuthenticated, IsOrgOperator]

    def post(self, request, task_uuid: str):
        org = require_org(request)
        serializer = RetryBackupDirectorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = retry_backup_directory(
                organization_id=org.id,
                task_uuid=str(task_uuid),
                backup_config_dir_id=int(serializer.validated_data["backup_config_dir_id"]),
            )
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
        return Response(result)
