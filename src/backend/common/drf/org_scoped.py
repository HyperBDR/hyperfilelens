"""DRF mixins for organization-scoped tenant APIs."""

from __future__ import annotations

from typing import Any

from django.db.models import QuerySet
from rest_framework.request import Request

from apps.iam.models import Organization
from apps.iam.org_context import require_org


class OrgScopedMixin:
    """
    Resolve the active organization from ``X-Org-Key`` / ``?org=`` and scope querysets.

    Subclasses may set ``org_scoped_skip_actions`` for endpoints that authenticate
    without a console user session (e.g. agent heartbeat).
    """

    org_lookup_field = "organization_id"
    org_scoped_skip_actions: tuple[str, ...] = ()

    _org: Organization | None = None

    @property
    def org(self) -> Organization:
        if self._org is None:
            self._org = require_org(self.request)
        return self._org

    def resolve_org_context(self) -> Organization:
        return self.org

    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        super().initial(request, *args, **kwargs)
        action = getattr(self, "action", None)
        if action not in self.org_scoped_skip_actions:
            _ = self.org

    def filter_queryset_by_org(self, queryset: QuerySet) -> QuerySet:
        action = getattr(self, "action", None)
        if action in self.org_scoped_skip_actions:
            return queryset
        return queryset.filter(**{self.org_lookup_field: self.org.id})

    def get_org_scoped_queryset(self) -> QuerySet:
        return super().get_queryset()

    def get_queryset(self) -> QuerySet:
        return self.filter_queryset_by_org(self.get_org_scoped_queryset())
