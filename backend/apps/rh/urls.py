from rest_framework.routers import DefaultRouter

from .conges_api import DemandeAbsenceViewSet
from .api import ContratViewSet, PieceViewSet, SalarieViewSet

router = DefaultRouter()
router.register("salaries", SalarieViewSet)
router.register("contrats", ContratViewSet)
router.register("pieces", PieceViewSet)
router.register("absences", DemandeAbsenceViewSet)

urlpatterns = router.urls
