from rest_framework.pagination import PageNumberPagination


class Pagination(PageNumberPagination):
    """Pages de 50 lignes ; les listes déroulantes peuvent en demander jusqu'à 200."""

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200
