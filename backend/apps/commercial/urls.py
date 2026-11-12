from rest_framework.routers import DefaultRouter

from .api import DevisViewSet

router = DefaultRouter()
router.register("devis", DevisViewSet)

urlpatterns = router.urls
