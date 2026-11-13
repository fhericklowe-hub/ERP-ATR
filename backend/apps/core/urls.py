from django.urls import path
from rest_framework.routers import DefaultRouter

from .pieces_api import PieceJointeViewSet
from .views import AccueilView, CompteViewSet, MoiView, MonMotDePasseView, PilotageView, ServiceViewSet, SiteViewSet, TraceViewSet, UtilisateurViewSet

router = DefaultRouter()
router.register("sites", SiteViewSet)
router.register("services", ServiceViewSet)
router.register("utilisateurs", UtilisateurViewSet)
router.register("comptes", CompteViewSet, basename="compte")
router.register("pieces-jointes", PieceJointeViewSet)
router.register("journal", TraceViewSet)

urlpatterns = [path("moi/", MoiView.as_view(), name="moi"), path("moi/mot-de-passe/", MonMotDePasseView.as_view(), name="mon-mot-de-passe"), path("accueil/", AccueilView.as_view(), name="accueil"),
               path("pilotage/", PilotageView.as_view(), name="pilotage"), *router.urls]
