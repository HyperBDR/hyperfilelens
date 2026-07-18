from rest_framework.pagination import PageNumberPagination


class AlertPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 300

    def get_page_size(self, request):
        if request.query_params.get("limit") and not request.query_params.get("page_size"):
            try:
                return min(int(request.query_params["limit"]), self.max_page_size)
            except (TypeError, ValueError):
                return self.page_size
        return super().get_page_size(request)
