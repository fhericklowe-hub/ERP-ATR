from django.apps import AppConfig
from django.db.models.signals import post_migrate


class HseConfig(AppConfig):
    name = "apps.hse"
    verbose_name = "HSE"

    def ready(self):
        from apps.core import pieces
        from apps.core import rappels as rappels_du_jour

        from .api import EvenementViewSet
        from .rappels import actions, epi, evenements
        from .roles import creer_roles
        from .terrain_api import VisiteViewSet

        post_migrate.connect(creer_roles, sender=self)
        pieces.declarer(EvenementViewSet)
        rappels_du_jour.declarer(evenements)
        rappels_du_jour.declarer(actions)
        pieces.declarer(VisiteViewSet)
        rappels_du_jour.declarer(epi)
