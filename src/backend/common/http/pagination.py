"""
Global pagination configuration.
"""

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class APIPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 10000
    page_query_param = "page"

    def get_paginated_response(self, data):
        return Response(
            {
                "data": {
                    "list": data,
                    "pagination": {
                        "total": self.page.paginator.count,
                        "page": self.page.number,
                        "pageSize": self.get_page_size(self.request),
                        "next": self.get_next_link(),
                        "previous": self.get_previous_link(),
                    },
                }
            }
        )

