from rest_framework.routers import DefaultRouter

from .commande_api import BonCommandeViewSet
from .reception_api import BonReceptionViewSet
from .views import AcheteurViewSet, DemandeAchatViewSet

router = DefaultRouter()
router.register("demandes", DemandeAchatViewSet)
router.register("bons-commande", BonCommandeViewSet)
router.register("bons-reception", BonReceptionViewSet)
router.register("acheteurs", AcheteurViewSet, basename="acheteur")

urlpatterns = router.urls
