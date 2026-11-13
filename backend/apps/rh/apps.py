from django.apps import AppConfig
from django.db.models.signals import post_migrate


class RhConfig(AppConfig):
    name = "apps.rh"
    verbose_name = "Ressources humaines"

    def ready(self):
        from apps.core import pieces
        from apps.core import rappels as rappels_du_jour

        from .api import SalarieViewSet
        from .rappels import echeances_du_personnel
        from .roles import creer_roles

        post_migrate.connect(creer_roles, sender=self)
        pieces.declarer(SalarieViewSet)
        rappels_du_jour.declarer(echeances_du_personnel)
