from decimal import Decimal

from django.db.models import Q, Sum
from django.http import HttpResponse
from rest_framework import exceptions, mixins, permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.achats.views import executer_transition
from apps.core.permissions import DroitsModele
from apps.referentiels.models import Article, Emplacement

from . import models as stock
from .imports import importer
from .models import BonSortie, LigneBonSortie, Mouvement, ReglageStock
from .pdf import pdf_bon_sortie

QUANTITE = serializers.DecimalField(max_digits=12, decimal_places=2)


def _objet(modele, pk, message, **filtres):
    try:
        return modele.objects.get(pk=pk, **filtres)
    except (modele.DoesNotExist, ValueError, TypeError):
        raise exceptions.ValidationError({"detail": message})


def _article(pk):
    return _objet(Article, pk, "Article inconnu.", actif=True)


def _magasin(pk):
    return _objet(Emplacement, pk, "Magasin inconnu.", type=Emplacement.Type.SITE)


class EtatStock(APIView):
    """État du stock : une ligne par article et par magasin.

    `?magasin=`, `?search=` (code ou désignation), `?alerte=1` (au seuil ou en dessous), `?article=`."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not request.user.has_perm("stock.view_mouvement"):
            raise exceptions.PermissionDenied()
        p = request.query_params
        mouvements = Mouvement.objects.all()
        reglages = ReglageStock.objects.all()
        if p.get("magasin"):
            mouvements, reglages = mouvements.filter(magasin_id=p["magasin"]), reglages.filter(magasin_id=p["magasin"])
        if p.get("article"):
            mouvements, reglages = mouvements.filter(article_id=p["article"]), reglages.filter(article_id=p["article"])
        if p.get("search"):
            q = Q(article__code__icontains=p["search"]) | Q(article__designation__icontains=p["search"])
            mouvements, reglages = mouvements.filter(q), reglages.filter(q)
        try:
            quantites = {(m["article"], m["magasin"]): m["q"]
                         for m in mouvements.values("article", "magasin").annotate(q=Sum("quantite"))}
            regles = {(r.article_id, r.magasin_id): r for r in reglages}
        except (ValueError, TypeError):
            raise exceptions.ValidationError({"detail": "Filtre invalide."})
        cles = set(quantites) | set(regles)
        articles = {a.id: a for a in Article.objects.filter(id__in={c[0] for c in cles}).select_related("unite")}
        magasins = dict(Emplacement.objects.filter(id__in={c[1] for c in cles}).values_list("id", "nom"))
        lignes = []
        for article_id, magasin_id in cles:
            a, regle = articles[article_id], regles.get((article_id, magasin_id))
            quantite = quantites.get((article_id, magasin_id), Decimal(0))
            seuil = regle.seuil_mini if regle else Decimal(0)
            lignes.append({
                "article": a.id, "code": a.code, "designation": a.designation, "unite": a.unite.code,
                "magasin": magasin_id, "magasin_nom": magasins[magasin_id], "quantite": str(quantite),
                "seuil_mini": str(seuil), "casier": regle.casier if regle else "", "reglage": regle.id if regle else None,
                "alerte": seuil > 0 and quantite <= seuil,
            })
        if p.get("alerte"):
            lignes = [l for l in lignes if l["alerte"]]
        lignes.sort(key=lambda l: (l["designation"].lower(), l["magasin_nom"]))
        return Response({"count": len(lignes), "results": lignes[:500],
                         "peut_ajuster": request.user.has_perm("stock.ajuster_stock"),
                         "peut_sortir": request.user.has_perm("stock.add_bonsortie")})


class MouvementSerializer(serializers.ModelSerializer):
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)
    article_nom = serializers.CharField(source="article.__str__", read_only=True)
    magasin_nom = serializers.CharField(source="magasin.nom", read_only=True)
    auteur_nom = serializers.SerializerMethodField()

    class Meta:
        model = Mouvement
        fields = ["id", "date", "type", "type_libelle", "article", "article_nom", "magasin", "magasin_nom", "quantite",
                  "prix_unitaire", "motif", "auteur_nom"]

    def get_auteur_nom(self, obj) -> str:
        return str(obj.auteur) if obj.auteur_id else ""


class MouvementViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Journal du stock, en lecture. Les écritures passent par les bons et par `ajuster` et `transferer`."""

    serializer_class = MouvementSerializer
    queryset = Mouvement.objects.select_related("article", "magasin", "auteur")
    permission_classes = [DroitsModele]
    filterset_fields = ["article", "magasin", "type"]
    search_fields = ["article__code", "article__designation", "motif"]

    ecriture = dict(detail=False, methods=["post"], permission_classes=[permissions.IsAuthenticated])

    def _ecrire(self, fonction, *args, **kwargs):
        from django.core.exceptions import PermissionDenied, ValidationError
        try:
            mouvement = fonction(self.request.user, *args, **kwargs)
        except PermissionDenied as e:
            raise exceptions.PermissionDenied(str(e))
        except ValidationError as e:
            raise exceptions.ValidationError({"detail": e.messages})
        return Response(self.get_serializer(mouvement).data, status=201)

    @action(**ecriture)
    def ajuster(self, request):
        d = request.data
        prix = d.get("prix_unitaire")
        prix = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0).run_validation(prix) if prix not in ("", None) else None
        return self._ecrire(stock.ajuster, _article(d.get("article")), _magasin(d.get("magasin")),
                            QUANTITE.run_validation(d.get("quantite")), str(d.get("motif", "")), prix)

    @action(**ecriture)
    def transferer(self, request):
        d = request.data
        return self._ecrire(stock.transferer, _article(d.get("article")), _magasin(d.get("origine")),
                            _magasin(d.get("destination")), QUANTITE.run_validation(d.get("quantite")), str(d.get("motif", "")))


    @action(detail=False, methods=["post"], permission_classes=[permissions.IsAuthenticated],
            parser_classes=[MultiPartParser, JSONParser])
    def importer(self, request):
        """Met le stock d'un magasin aux quantités d'un classeur Excel. `simuler=1` contrôle sans écrire."""
        from django.core.exceptions import PermissionDenied, ValidationError
        fichier = request.FILES.get("fichier")
        if not fichier:
            raise exceptions.ValidationError({"detail": "Choisissez un classeur Excel."})
        if fichier.size > 5 * 1024 * 1024:
            raise exceptions.ValidationError({"detail": "Fichier trop lourd : 5 Mo au plus."})
        try:
            bilan = importer(request.user, fichier, _magasin(request.data.get("magasin")),
                             simuler=str(request.data.get("simuler", "")).lower() in ("1", "true", "on"))
        except PermissionDenied as e:
            raise exceptions.PermissionDenied(str(e))
        except ValidationError as e:
            raise exceptions.ValidationError({"detail": e.messages})
        return Response(bilan)


class ReglageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReglageStock
        fields = ["id", "article", "magasin", "seuil_mini", "casier"]


class ReglageViewSet(mixins.CreateModelMixin, mixins.UpdateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """Seuil d'alerte et rangement d'un article dans un magasin."""

    serializer_class = ReglageSerializer
    queryset = ReglageStock.objects.all()
    permission_classes = [DroitsModele]
    filterset_fields = ["article", "magasin"]


class LigneSortieSerializer(serializers.ModelSerializer):
    code = serializers.CharField(source="article.code", read_only=True)
    designation = serializers.CharField(source="article.designation", read_only=True)
    unite = serializers.CharField(source="article.unite.code", read_only=True)

    class Meta:
        model = LigneBonSortie
        fields = ["id", "article", "code", "designation", "unite", "quantite"]


class BonSortieSerializer(serializers.ModelSerializer):
    lignes = LigneSortieSerializer(many=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    magasin_nom = serializers.CharField(source="magasin.nom", read_only=True)
    remis_a_nom = serializers.CharField(source="remis_a.__str__", read_only=True)
    magasinier_nom = serializers.CharField(source="magasinier.__str__", read_only=True)
    service_nom = serializers.CharField(source="service.nom", read_only=True, default="")
    annule_par_nom = serializers.SerializerMethodField()
    peut_annuler = serializers.SerializerMethodField()
    numero_or = serializers.CharField(max_length=40, allow_blank=True, required=False)

    class Meta:
        model = BonSortie
        fields = ["id", "numero", "statut", "statut_libelle", "date", "magasin", "magasin_nom", "numero_or", "materiel",
                  "remis_a", "remis_a_nom", "service", "service_nom", "observations", "magasinier_nom", "cree_le",
                  "annule_par_nom", "annule_le", "motif_annulation", "peut_annuler", "lignes"]
        read_only_fields = ["numero", "statut", "annule_le", "motif_annulation"]

    def get_annule_par_nom(self, obj) -> str:
        return str(obj.annule_par) if obj.annule_par_id else ""

    def get_peut_annuler(self, obj) -> bool:
        return obj.peut_annuler(self.context["request"].user)

    def create(self, donnees):
        from django.core.exceptions import PermissionDenied, ValidationError
        lignes = [(l["article"], l["quantite"]) for l in donnees.pop("lignes", [])]
        try:
            return BonSortie.enregistrer(self.context["request"].user, lignes, **donnees)
        except PermissionDenied as e:
            raise exceptions.PermissionDenied(str(e))
        except ValidationError as e:
            raise exceptions.ValidationError({"detail": e.messages})


class BonSortieViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """Bons de sortie. Un bon enregistré ne se modifie pas : il s'annule, et les pièces reviennent en stock."""

    serializer_class = BonSortieSerializer
    queryset = BonSortie.objects.select_related("magasin", "remis_a", "magasinier", "service", "annule_par").prefetch_related(
        "lignes__article__unite")
    permission_classes = [DroitsModele]
    filterset_fields = ["statut", "magasin", "remis_a", "service", "numero_or"]
    search_fields = ["numero", "numero_or", "materiel", "lignes__article__code", "lignes__article__designation"]

    def get_queryset(self):
        return super().get_queryset().distinct() if self.request.query_params.get("search") else super().get_queryset()

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def annuler(self, request, pk=None):
        executer_transition(self.get_object(), "annuler", request.user, request.data.get("commentaire", ""))
        return Response(self.get_serializer(self.get_object()).data)

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        bon = self.get_object()
        reponse = HttpResponse(pdf_bon_sortie(bon), content_type="application/pdf")
        reponse["Content-Disposition"] = f'inline; filename="{bon.numero}.pdf"'
        return reponse
