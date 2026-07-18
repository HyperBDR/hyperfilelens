from rest_framework.permissions import BasePermission

from apps.iam.access import get_access_profile


class HasRequiredFeature(BasePermission):
    """
    Allow access when the user can see view.required_feature.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        required_feature = getattr(view, "required_feature", "")
        if not required_feature:
            return False

        org_key = request.headers.get("X-Org-Key") or request.query_params.get("org")
        profile = get_access_profile(user, org_key=org_key)
        return required_feature in (profile.get("visible_features") or [])

