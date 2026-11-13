from rest_framework.routers import DefaultRouter

from .api import ActionViewSet, EvenementViewSet
from .terrain_api import DotationViewSet, VisiteViewSet

router = DefaultRouter()
router.register("evenements", EvenementViewSet)
router.register("actions", ActionViewSet)
router.register("visites", VisiteViewSet)
router.register("epi", DotationViewSet)

urlpatterns = router.urls
