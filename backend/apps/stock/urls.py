from django.urls import path
from rest_framework.routers import DefaultRouter

from .demandes_api import DemandeSortieViewSet
from .api import BonSortieViewSet, EtatStock, MouvementViewSet, ReglageViewSet

router = DefaultRouter()
router.register("mouvements", MouvementViewSet)
router.register("reglages", ReglageViewSet)
router.register("sorties", BonSortieViewSet)
router.register("demandes", DemandeSortieViewSet)

urlpatterns = [path("etat/", EtatStock.as_view(), name="etat-stock"), *router.urls]
