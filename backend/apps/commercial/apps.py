from django.apps import AppConfig
from django.db.models.signals import post_migrate


class CommercialConfig(AppConfig):
    name = "apps.commercial"
    verbose_name = "Commercial"

    def ready(self):
        from apps.core import pieces

        from .api import DevisViewSet
        from .roles import creer_roles

        post_migrate.connect(creer_roles, sender=self)
        pieces.declarer(DevisViewSet)
