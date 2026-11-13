from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import exceptions, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.core.api import VueMetier
from apps.core.models import Compteur

from .imports import importer
from .models import Article, CompteCharge, Projet, Contact, Emplacement, FamilleArticle, Tiers, Unite
from .serializers import (
    CompteChargeSerializer, ProjetSerializer,
    ArticleSerializer, ContactSerializer, EmplacementSerializer, FamilleArticleSerializer,
    TiersSerializer, UniteSerializer,
)


class TiersViewSet(VueMetier):
    queryset = Tiers.objects.prefetch_related("contacts")
    serializer_class = TiersSerializer
    filterset_fields = ["est_client", "est_fournisseur", "actif"]
    search_fields = ["code", "raison_sociale", "ville", "numero_contribuable"]
    ordering_fields = ["raison_sociale", "code"]
    http_method_names = ["get", "post", "patch", "put", "head", "options"]   # un tiers ne se supprime pas : on le désactive

    @transaction.atomic
    def perform_create(self, serializer):
        code = serializer.validated_data.get("code") or ""
        while not code or Tiers.objects.filter(code=code).exists():   # sans code saisi : numéro automatique
            code = f"T{Compteur.suivant('TIERS'):05d}"
        serializer.save(code=code, cree_par=self.request.user, modifie_par=self.request.user)

    @action(detail=False, methods=["post"], permission_classes=[permissions.IsAuthenticated],
            parser_classes=[MultiPartParser, JSONParser])
    def importer(self, request):
        """Crée ou met à jour des fournisseurs ou des clients (`qualite`) depuis un classeur Excel. `simuler=1` contrôle sans écrire."""
        fichier = request.FILES.get("fichier")
        if not fichier:
            raise exceptions.ValidationError({"detail": "Choisissez un classeur Excel."})
        if fichier.size > 5 * 1024 * 1024:
            raise exceptions.ValidationError({"detail": "Fichier trop lourd : 5 Mo au plus."})
        try:
            bilan = importer(request.user, fichier, str(request.data.get("qualite", "")),
                             simuler=str(request.data.get("simuler", "")).lower() in ("1", "true", "on"))
        except PermissionDenied as e:
            raise exceptions.PermissionDenied(str(e))
        except DjangoValidationError as e:
            raise exceptions.ValidationError({"detail": e.messages})
        return Response(bilan)


class DroitsContact(permissions.BasePermission):
    """Les contacts suivent les droits de la fiche du tiers : les voir avec elle, les tenir à jour si on peut la modifier."""

    def has_permission(self, request, view):
        droit = "view_tiers" if request.method in permissions.SAFE_METHODS else "change_tiers"
        return bool(request.user and request.user.is_authenticated and request.user.has_perm(f"referentiels.{droit}"))


class ContactViewSet(VueMetier):
    permission_classes = [DroitsContact]
    queryset = Contact.objects.select_related("tiers")
    serializer_class = ContactSerializer
    filterset_fields = ["tiers"]
    search_fields = ["nom", "email"]


class EmplacementViewSet(VueMetier):
    queryset = Emplacement.objects.select_related("site", "client")
    serializer_class = EmplacementSerializer
    filterset_fields = ["type", "site", "client", "actif"]
    search_fields = ["nom", "ville"]


class UniteViewSet(viewsets.ModelViewSet):
    queryset = Unite.objects.all()
    serializer_class = UniteSerializer


class FamilleArticleViewSet(viewsets.ModelViewSet):
    queryset = FamilleArticle.objects.all()
    serializer_class = FamilleArticleSerializer
    search_fields = ["code", "nom"]


class ArticleViewSet(VueMetier):
    queryset = Article.objects.select_related("famille", "unite")
    serializer_class = ArticleSerializer
    filterset_fields = ["nature", "famille", "gere_en_stock", "actif"]
    search_fields = ["code", "designation"]
    ordering_fields = ["designation", "code"]
    http_method_names = ["get", "post", "patch", "put", "head", "options"]   # un article ne se supprime pas : on le désactive


class CompteChargeViewSet(viewsets.ModelViewSet):
    queryset = CompteCharge.objects.all()
    serializer_class = CompteChargeSerializer
    filterset_fields = ["actif"]
    search_fields = ["numero", "libelle", "article_ng"]
    pagination_class = None


class ProjetViewSet(viewsets.ModelViewSet):
    queryset = Projet.objects.all()
    serializer_class = ProjetSerializer
    filterset_fields = ["actif", "activite", "type"]
    search_fields = ["nom", "code_analytique"]
    pagination_class = None
