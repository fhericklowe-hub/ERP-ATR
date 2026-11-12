from django.apps import AppConfig
from django.db.models.signals import post_migrate


class MoyensConfig(AppConfig):
    name = "apps.moyens"
    verbose_name = "Moyens généraux"

    def ready(self):
        from .roles import creer_roles

        post_migrate.connect(creer_roles, sender=self)
        from apps.core import pieces

        from .api import BienViewSet, DemandeInterventionViewSet
        from .contrats_api import ContratViewSet, EcheanceViewSet

        for vue in (BienViewSet, DemandeInterventionViewSet, ContratViewSet, EcheanceViewSet):
            pieces.declarer(vue)
        from apps.core import rappels as rappels_du_jour

        from .rappels import echeances

        rappels_du_jour.declarer(echeances)
