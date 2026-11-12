from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import MoiView, ServiceViewSet, SiteViewSet, UtilisateurViewSet

router = DefaultRouter()
router.register("sites", SiteViewSet)
router.register("services", ServiceViewSet)
router.register("utilisateurs", UtilisateurViewSet)

urlpatterns = [path("moi/", MoiView.as_view(), name="moi"), *router.urls]
