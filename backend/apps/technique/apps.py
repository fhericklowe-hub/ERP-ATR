from django.apps import AppConfig
from django.db.models.signals import post_migrate


class TechniqueConfig(AppConfig):
    name = "apps.technique"
    verbose_name = "Technique"

    def ready(self):
        from apps.core import pieces

        from .api import MaterielViewSet, OrdreReparationViewSet
        from .roles import creer_roles

        post_migrate.connect(creer_roles, sender=self)
        pieces.declarer(MaterielViewSet)
        pieces.declarer(OrdreReparationViewSet)
        from apps.core import rappels as rappels_du_jour

        from .rappels import entretiens, ordres_a_cloturer

        rappels_du_jour.declarer(entretiens)
        rappels_du_jour.declarer(ordres_a_cloturer)
