from rest_framework import viewsets

from apps.core.api import VueMetier

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
    search_fields = ["code", "raison_sociale", "ville"]


class ContactViewSet(VueMetier):
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
