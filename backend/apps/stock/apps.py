from django.apps import AppConfig
from django.db.models.signals import post_migrate


class StockConfig(AppConfig):
    name = "apps.stock"
    verbose_name = "Stock"

    def ready(self):
        from apps.achats import signaux
        from apps.core import pieces

        from . import receptions
        from .api import BonSortieViewSet
        from .roles import creer_roles

        post_migrate.connect(creer_roles, sender=self)
        signaux.reception_validee.connect(receptions.entrer_en_stock, dispatch_uid="stock.entree_reception")
        signaux.reception_annulee.connect(receptions.annuler_entree, dispatch_uid="stock.annulation_reception")
        pieces.declarer(BonSortieViewSet)
