from django.contrib.auth.models import Group
from django.db import transaction
from rest_framework import exceptions, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .api import VueMetier
from .export import ExportExcel
from .models import Service, Site, Trace, Utilisateur
from .serializers import CompteSerializer, TraceSerializer, ServiceSerializer, SiteSerializer, UtilisateurSerializer


class SiteViewSet(VueMetier):
    queryset = Site.objects.all()
    serializer_class = SiteSerializer
    filterset_fields = ["actif", "est_siege"]
    search_fields = ["code", "nom", "ville"]


class ServiceViewSet(VueMetier):
    queryset = Service.objects.select_related("responsable")
    serializer_class = ServiceSerializer
    filterset_fields = ["actif"]
    search_fields = ["code", "nom"]


class UtilisateurViewSet(viewsets.ReadOnlyModelViewSet):
    """Annuaire des utilisateurs. Les comptes se gèrent dans l'administration."""

    queryset = Utilisateur.objects.select_related("site", "service").prefetch_related("groups")
    serializer_class = UtilisateurSerializer
    filterset_fields = ["site", "service", "is_active"]
    search_fields = ["username", "first_name", "last_name", "email"]


class GereLesComptes(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.has_perm("core.gerer_comptes"))


class CompteViewSet(viewsets.ModelViewSet):
    """Gestion des comptes : création, rôles, mot de passe, désactivation. Un compte ne se supprime pas."""

    permission_classes = [GereLesComptes]
    queryset = Utilisateur.objects.select_related("site", "service").prefetch_related("groups")
    serializer_class = CompteSerializer
    filterset_fields = ["site", "service", "is_active"]
    search_fields = ["username", "first_name", "last_name", "email", "fonction"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    @transaction.atomic
    def perform_create(self, serializer):
        serializer.save()

    @transaction.atomic
    def perform_update(self, serializer):
        serializer.save()

    @action(detail=False)
    def roles(self, request):
        """Les rôles attribuables, par ordre alphabétique (donc regroupés par module)."""
        return Response(list(Group.objects.order_by("name").values_list("name", flat=True)))


class MoiView(APIView):
    """Profil et droits de l'utilisateur connecté, pour construire les menus de l'application."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UtilisateurSerializer(request.user).data)


class MonMotDePasseView(APIView):
    """Chacun change son propre mot de passe, en donnant l'actuel. Les autres sessions du compte sont fermées ;
    celle-ci reçoit de nouveaux jetons pour rester ouverte."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError
        from rest_framework_simplejwt.tokens import RefreshToken

        actuel, nouveau = str(request.data.get("actuel", "")), str(request.data.get("nouveau", ""))
        if not request.user.check_password(actuel):
            raise exceptions.ValidationError({"actuel": "Le mot de passe actuel n'est pas le bon."})
        if nouveau == actuel:
            raise exceptions.ValidationError({"nouveau": "Le nouveau mot de passe doit être différent de l'actuel."})
        try:
            validate_password(nouveau, request.user)
        except ValidationError as e:
            raise exceptions.ValidationError({"nouveau": list(e.messages)})
        request.user.set_password(nouveau)
        request.user.mot_de_passe_a_changer = False
        request.user.save(update_fields=["password", "mot_de_passe_a_changer"])
        jetons = RefreshToken.for_user(request.user)
        return Response({"access": str(jetons.access_token), "refresh": str(jetons)})


class AccueilView(APIView):
    """Ce qui attend l'utilisateur connecté, toutes rubriques confondues : les mêmes points que le rappel par e-mail."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from . import rappels

        return Response(rappels.accueil(request.user))


class PilotageView(APIView):
    """Tableau de bord de direction : les chiffres clés de chaque module."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from . import pilotage

        if not request.user.has_perm("core.voir_pilotage"):
            raise exceptions.PermissionDenied()
        return Response(pilotage.tableau())


class TraceViewSet(ExportExcel, viewsets.ReadOnlyModelViewSet):
    """Journal des modifications, en lecture seule (droit « voir » le journal)."""

    queryset = Trace.objects.select_related("utilisateur")
    serializer_class = TraceSerializer
    filterset_fields = {"action": ["exact"], "modele": ["exact"], "utilisateur": ["exact"], "date": ["gte", "lte"], "objet_id": ["exact"]}
    search_fields = ["objet_libelle", "modele"]
    export_titre, export_fichier = "Journal des modifications", "journal"
    export_colonnes = [("Date", "date", "date"), ("Utilisateur", "utilisateur_nom"), ("Action", "action_libelle"), ("Type", "modele_libelle"),
                       ("Objet", "objet_libelle")]
