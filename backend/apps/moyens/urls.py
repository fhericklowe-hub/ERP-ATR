from rest_framework.routers import DefaultRouter

from .api import BienViewSet, DemandeInterventionViewSet
from .contrats_api import ContratViewSet, EcheanceViewSet

router = DefaultRouter()
router.register("biens", BienViewSet)
router.register("interventions", DemandeInterventionViewSet)
router.register("contrats", ContratViewSet)
router.register("echeances", EcheanceViewSet)

urlpatterns = router.urls
