from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.iam.org_context import require_org
from apps.iam.permissions_org import IsOrgOperator
from apps.restore.services import interface as restore_services


def _validation_error(exc: DjangoValidationError) -> ValidationError:
    if hasattr(exc, "message_dict"):
        return ValidationError(exc.message_dict)
    return ValidationError({"detail": exc.messages})


class RestoreTaskCancelView(APIView):
    permission_classes = [IsAuthenticated, IsOrgOperator]

    def post(self, request, task_uuid: str):
        org = require_org(request)
        reason = str(request.data.get("reason") or "").strip()
        try:
            result = restore_services.cancel_restore(
                organization_id=org.id,
                task_uuid=str(task_uuid),
                reason=reason,
            )
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
        return Response(result)
