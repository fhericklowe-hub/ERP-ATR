from rest_framework.routers import DefaultRouter

from .api import DevisViewSet
from .opportunite_api import OpportuniteViewSet

router = DefaultRouter()
router.register("devis", DevisViewSet)
router.register("opportunites", OpportuniteViewSet)

urlpatterns = router.urls
