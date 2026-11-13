from rest_framework.routers import DefaultRouter

from .api import ContratViewSet, PieceViewSet, SalarieViewSet

router = DefaultRouter()
router.register("salaries", SalarieViewSet)
router.register("contrats", ContratViewSet)
router.register("pieces", PieceViewSet)

urlpatterns = router.urls
