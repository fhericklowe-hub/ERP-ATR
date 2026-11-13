from django.urls import path
from rest_framework.routers import DefaultRouter

from .pieces_api import PieceJointeViewSet
from .views import AccueilView, CompteViewSet, MoiView, PilotageView, ServiceViewSet, SiteViewSet, UtilisateurViewSet

router = DefaultRouter()
router.register("sites", SiteViewSet)
router.register("services", ServiceViewSet)
router.register("utilisateurs", UtilisateurViewSet)
router.register("comptes", CompteViewSet, basename="compte")
router.register("pieces-jointes", PieceJointeViewSet)

urlpatterns = [path("moi/", MoiView.as_view(), name="moi"), path("accueil/", AccueilView.as_view(), name="accueil"),
               path("pilotage/", PilotageView.as_view(), name="pilotage"), *router.urls]
