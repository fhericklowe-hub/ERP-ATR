from rest_framework import permissions, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .api import VueMetier
from .models import Service, Site, Utilisateur
from .serializers import ServiceSerializer, SiteSerializer, UtilisateurSerializer


class SiteViewSet(VueMetier):
    queryset = Site.objects.all()
    serializer_class = SiteSerializer
    filterset_fields = ["actif", "est_siege"]
    search_fields = ["code", "nom", "ville"]


class ServiceViewSet(VueMetier):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
    filterset_fields = ["actif"]
    search_fields = ["code", "nom"]


class UtilisateurViewSet(viewsets.ReadOnlyModelViewSet):
    """Annuaire des utilisateurs. Les comptes se gèrent dans l'administration."""

    queryset = Utilisateur.objects.select_related("site", "service").prefetch_related("groups")
    serializer_class = UtilisateurSerializer
    filterset_fields = ["site", "service", "is_active"]
    search_fields = ["username", "first_name", "last_name", "email"]


class MoiView(APIView):
    """Profil et droits de l'utilisateur connecté, pour construire les menus de l'application."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UtilisateurSerializer(request.user).data)


class AccueilView(APIView):
    """Ce qui attend l'utilisateur connecté, toutes rubriques confondues : les mêmes points que le rappel par e-mail."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from . import rappels

        return Response(rappels.accueil(request.user))
