from django.urls import path
from rest_framework.routers import DefaultRouter

from .demandes_api import DemandeSortieViewSet
from .valorisation_api import Consommations, ValeurStock
from .api import BonSortieViewSet, EtatStock, MouvementViewSet, ReglageViewSet

router = DefaultRouter()
router.register("mouvements", MouvementViewSet)
router.register("reglages", ReglageViewSet)
router.register("sorties", BonSortieViewSet)
router.register("demandes", DemandeSortieViewSet)

urlpatterns = [path("etat/", EtatStock.as_view(), name="etat-stock"),
               path("valeur/", ValeurStock.as_view(), name="valeur-stock"),
               path("consommations/", Consommations.as_view(), name="consommations-stock"), *router.urls]
