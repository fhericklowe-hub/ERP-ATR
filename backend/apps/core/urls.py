from django.urls import path
from rest_framework.routers import DefaultRouter

from .pieces_api import PieceJointeViewSet
from .views import MoiView, ServiceViewSet, SiteViewSet, UtilisateurViewSet

router = DefaultRouter()
router.register("sites", SiteViewSet)
router.register("services", ServiceViewSet)
router.register("utilisateurs", UtilisateurViewSet)
router.register("pieces-jointes", PieceJointeViewSet)

urlpatterns = [path("moi/", MoiView.as_view(), name="moi"), *router.urls]
