from rest_framework.routers import DefaultRouter

from .api import MaterielViewSet, OrdreReparationViewSet, PlanEntretienViewSet

router = DefaultRouter()
router.register("materiels", MaterielViewSet)
router.register("ordres", OrdreReparationViewSet)
router.register("plans", PlanEntretienViewSet)

urlpatterns = router.urls
