from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("api/", include("apps.core.urls")),
    path("api/", include("apps.referentiels.urls")),
    path("api/achats/", include("apps.achats.urls")),
    path("api/moyens/", include("apps.moyens.urls")),
    path("api/stock/", include("apps.stock.urls")),
    path("api/technique/", include("apps.technique.urls")),
]

# En développement, Django sert lui-même les fichiers joints ; en production c'est Nginx.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
