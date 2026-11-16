from rest_framework.routers import DefaultRouter

from .api import OrdreTransportViewSet

router = DefaultRouter()
router.register("ordres", OrdreTransportViewSet)

urlpatterns = router.urls
