"""Tenant-console read-only Provider Catalog API."""

from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.storage.selectors.interface import get_effective_provider_catalog


class StorageProviderCatalogView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, _request):
        return Response(get_effective_provider_catalog())
