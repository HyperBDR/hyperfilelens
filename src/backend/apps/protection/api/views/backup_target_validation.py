from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.iam.org_context import require_org
from apps.iam.permissions_org import IsOrgOperator
from apps.protection.api.serializers.backup_target_validation import (
    BackupTargetValidationSerializer,
)
from apps.protection.services.backup_target_validation import validate_backup_targets


class BackupTargetValidationView(APIView):
    permission_classes = [IsAuthenticated, IsOrgOperator]

    def post(self, request):
        org = require_org(request)
        serializer = BackupTargetValidationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            validate_backup_targets(
                organization_id=org.id,
                sources=serializer.validated_data["sources"],
            )
        )
