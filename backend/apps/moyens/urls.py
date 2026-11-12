from rest_framework.routers import DefaultRouter

from .api import BienViewSet, DemandeInterventionViewSet

router = DefaultRouter()
router.register("biens", BienViewSet)
router.register("interventions", DemandeInterventionViewSet)

urlpatterns = router.urls
