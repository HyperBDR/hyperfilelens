"""
User-related views.
"""

from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.iam.auth.serializers import UserDetailsSerializer


class CustomUserDetailsView(RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        return UserDetailsSerializer

    def get_object(self):
        # Check if auth_error was set (force logout detected)
        auth_error = getattr(self.request, 'auth_error', None)
        if auth_error:
            error_code = auth_error.get("error_code", "OTHER_DEVICE_LOGIN")
            message = auth_error.get("message", _("Your account was logged in from another device"))
            raise AuthenticationFailed(
                detail={"error_code": error_code, "message": message},
                code=error_code.lower(),
            )
        return self.request.user

    def get(self, request, *args, **kwargs):
        user = self.get_object()
        serializer = self.get_serializer(user)
        return Response(serializer.data)

