from django.conf import settings
from rest_framework.pagination import PageNumberPagination


class LimitedPageNumberPagination(PageNumberPagination):
    """
    A more specialized instance of PageNumberPagination which allows the API
    caller to define the number of items on each page
    """

    page_size_query_param = "page_size"
    max_page_size = settings.REST_FRAMEWORK["PAGE_SIZE"] * 3
