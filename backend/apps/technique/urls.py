from rest_framework.routers import DefaultRouter

from .carburant import PleinViewSet
from .classement import CoutsParcViewSet
from .api import MaterielViewSet, OrdreReparationViewSet, PlanEntretienViewSet

router = DefaultRouter()
router.register("materiels", MaterielViewSet)
router.register("ordres", OrdreReparationViewSet)
router.register("plans", PlanEntretienViewSet)
router.register("pleins", PleinViewSet)
router.register("couts-parc", CoutsParcViewSet, basename="couts-parc")

urlpatterns = router.urls
