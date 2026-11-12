from rest_framework.routers import DefaultRouter

from .api import MaterielViewSet, OrdreReparationViewSet

router = DefaultRouter()
router.register("materiels", MaterielViewSet)
router.register("ordres", OrdreReparationViewSet)

urlpatterns = router.urls
