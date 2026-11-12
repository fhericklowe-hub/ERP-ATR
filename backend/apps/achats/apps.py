from django.apps import AppConfig
from django.db.models.signals import post_migrate


class AchatsConfig(AppConfig):
    name = "apps.achats"
    verbose_name = "Achats"

    def ready(self):
        from .roles import creer_roles

        post_migrate.connect(creer_roles, sender=self)
        from apps.core import pieces

        from .budget_api import DemandeBudgetViewSet
        from .commande_api import BonCommandeViewSet
        from .reception_api import BonReceptionViewSet
        from .views import DemandeAchatViewSet

        for vue in (DemandeAchatViewSet, DemandeBudgetViewSet, BonCommandeViewSet, BonReceptionViewSet):
            pieces.declarer(vue)
