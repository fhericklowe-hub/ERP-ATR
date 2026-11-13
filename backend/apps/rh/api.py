import datetime

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from rest_framework import exceptions, permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.achats.views import executer_transition
from apps.core.api import VueMetier

from .models import Contrat, PieceSalarie, Salarie, echeances


class _Verifie(serializers.ModelSerializer):
    """Applique les contrôles du modèle (`clean`) à la saisie."""

    def validate(self, attrs):
        valeurs = {c: getattr(self.instance, c) for c in self.Meta.verifies} if self.instance else {}
        valeurs.update({c: v for c, v in attrs.items() if c in self.Meta.verifies})
        essai = self.Meta.model(**valeurs)
        essai.id = self.instance.id if self.instance else None
        try:
            essai.clean()
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.message_dict)
        return attrs


class ContratSerializer(_Verifie):
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = Contrat
        fields = ["id", "salarie", "type", "type_libelle", "date_debut", "date_fin", "fin_essai", "fonction", "observations"]
        verifies = ["type", "date_debut", "date_fin", "fin_essai"]


class PieceSerializer(_Verifie):
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = PieceSalarie
        fields = ["id", "salarie", "type", "type_libelle", "libelle", "numero", "date_delivrance", "date_expiration"]
        verifies = ["date_delivrance", "date_expiration"]


class SalarieSerializer(_Verifie):
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    categorie_libelle = serializers.CharField(source="get_categorie_display", read_only=True)
    situation_libelle = serializers.CharField(source="get_situation_familiale_display", read_only=True)
    nom_complet = serializers.CharField(source="__str__", read_only=True)
    site_nom = serializers.CharField(source="site.nom", read_only=True)
    service_nom = serializers.CharField(source="service.nom", read_only=True, default="")
    responsable_nom = serializers.SerializerMethodField()
    utilisateur_nom = serializers.CharField(source="utilisateur.username", read_only=True, default="")
    anciennete = serializers.IntegerField(read_only=True)
    contrat = serializers.SerializerMethodField()
    contrats = ContratSerializer(many=True, read_only=True)
    pieces = PieceSerializer(many=True, read_only=True)
    peut_modifier = serializers.SerializerMethodField()
    peut_sortir = serializers.SerializerMethodField()

    class Meta:
        model = Salarie
        fields = ["id", "matricule", "statut", "statut_libelle", "nom", "prenoms", "nom_complet", "sexe", "date_naissance",
                  "lieu_naissance", "nationalite", "situation_familiale", "situation_libelle", "enfants", "telephone", "email",
                  "adresse", "contact_urgence", "telephone_urgence", "numero_cnps", "site", "site_nom", "service", "service_nom",
                  "fonction", "categorie", "categorie_libelle", "responsable", "responsable_nom", "utilisateur", "utilisateur_nom",
                  "date_embauche", "date_sortie", "motif_sortie", "observations", "conges_solde_depart", "conges_depuis", "anciennete", "contrat", "contrats", "pieces",
                  "peut_modifier", "peut_sortir"]
        verifies = ["date_naissance", "date_embauche", "responsable"]

    def get_responsable_nom(self, obj) -> str:
        return str(obj.responsable) if obj.responsable_id else ""

    def get_contrat(self, obj) -> str:
        c = obj.contrat_en_cours
        return c.get_type_display() if c else ""

    def get_peut_modifier(self, obj) -> bool:
        return self.context["request"].user.has_perm("rh.change_salarie")

    def get_peut_sortir(self, obj) -> bool:
        return self.context["request"].user.has_perm("rh.gerer_sortie_salarie")


def _jour(valeur):
    try:
        return datetime.date.fromisoformat(str(valeur)) if valeur else None
    except ValueError:
        raise exceptions.ValidationError({"detail": "Date invalide."})


class SalarieViewSet(VueMetier):
    """Dossiers du personnel. Un salarié ne se supprime pas : on enregistre sa sortie des effectifs."""

    serializer_class = SalarieSerializer
    queryset = Salarie.objects.select_related("site", "service", "responsable", "utilisateur").prefetch_related("contrats", "pieces")
    filterset_fields = ["statut", "site", "service", "categorie", "responsable"]
    search_fields = ["matricule", "nom", "prenoms", "fonction", "telephone"]
    ordering_fields = ["nom", "matricule", "date_embauche"]
    http_method_names = ["get", "post", "patch", "put", "head", "options"]

    transition = dict(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])

    def _transition(self, request, nom, *args):
        if not request.user.has_perm("rh.view_salarie"):
            raise exceptions.PermissionDenied()
        executer_transition(self.get_object(), nom, request.user, *args)
        return Response(self.get_serializer(self.get_object()).data)

    @action(**transition)
    def sortir(self, request, pk=None):
        return self._transition(request, "sortir", _jour(request.data.get("date_sortie")), str(request.data.get("motif", "")))

    @action(**transition)
    def reintegrer(self, request, pk=None):
        return self._transition(request, "reintegrer")

    @action(detail=False, methods=["get"])
    def echeances(self, request):
        """Pièces à renouveler, fins de contrat et de période d'essai. `?jours=` (30 par défaut), `?site=`, `?service=`."""
        p = request.query_params
        try:
            jours = min(max(int(p.get("jours") or 30), 0), 365)
            filtre = Q(statut=Salarie.Statut.ACTIF)
            if p.get("site"):
                filtre &= Q(site_id=int(p["site"]))
            if p.get("service"):
                filtre &= Q(service_id=int(p["service"]))
        except ValueError:
            raise exceptions.ValidationError({"detail": "Filtre invalide."})
        return Response(echeances(jours, Salarie.objects.filter(filtre)))

    @action(detail=False, methods=["get"])
    def effectifs(self, request):
        """Nombre de salariés en poste, par site et par service."""
        from django.db.models import Count

        actifs = Salarie.objects.filter(statut=Salarie.Statut.ACTIF)
        return Response({
            "total": actifs.count(),
            "par_site": list(actifs.values("site__nom").annotate(n=Count("id")).order_by("site__nom").values_list("site__nom", "n")),
            "par_service": [(nom or "Sans service", n) for nom, n in
                            actifs.values("service__nom").annotate(n=Count("id")).order_by("service__nom").values_list("service__nom", "n")],
        })


class _DuDossier(VueMetier):
    """Contrats et pièces : saisis et corrigés par le gestionnaire RH, sur le dossier d'un salarié."""

    filterset_fields = ["salarie", "type"]

    def perform_update(self, serializer):
        if "salarie" in serializer.validated_data and serializer.validated_data["salarie"] != serializer.instance.salarie:
            raise exceptions.ValidationError({"salarie": "Une ligne ne change pas de dossier."})
        super().perform_update(serializer)


class ContratViewSet(_DuDossier):
    serializer_class = ContratSerializer
    queryset = Contrat.objects.select_related("salarie")


class PieceViewSet(_DuDossier):
    serializer_class = PieceSerializer
    queryset = PieceSalarie.objects.select_related("salarie")
