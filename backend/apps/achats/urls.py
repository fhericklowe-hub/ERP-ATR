from rest_framework.routers import DefaultRouter

from .views import AcheteurViewSet, DemandeAchatViewSet

router = DefaultRouter()
router.register("demandes", DemandeAchatViewSet)
router.register("acheteurs", AcheteurViewSet, basename="acheteur")

urlpatterns = router.urls
