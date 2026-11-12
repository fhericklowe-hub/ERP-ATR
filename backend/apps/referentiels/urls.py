from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("tiers", views.TiersViewSet)
router.register("contacts", views.ContactViewSet)
router.register("emplacements", views.EmplacementViewSet)
router.register("unites", views.UniteViewSet)
router.register("familles-articles", views.FamilleArticleViewSet)
router.register("articles", views.ArticleViewSet)
router.register("comptes-charge", views.CompteChargeViewSet)
router.register("projets", views.ProjetViewSet)

urlpatterns = router.urls
