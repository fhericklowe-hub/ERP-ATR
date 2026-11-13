from rest_framework.routers import DefaultRouter

from .api import ActionViewSet, EvenementViewSet

router = DefaultRouter()
router.register("evenements", EvenementViewSet)
router.register("actions", ActionViewSet)

urlpatterns = router.urls
