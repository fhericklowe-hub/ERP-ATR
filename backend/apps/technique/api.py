from rest_framework import exceptions, mixins, permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.achats.views import executer_transition
from apps.core.api import VueMetier
from apps.core.models import Utilisateur

from .models import Materiel, OrdreReparation

HEURES = serializers.DecimalField(max_digits=10, decimal_places=1, min_value=0, allow_null=True)
KM = serializers.IntegerField(min_value=0, allow_null=True)


def _nombre(champ, valeur):
    return champ.run_validation(valeur if valeur not in ("", None) else None)


class MaterielSerializer(serializers.ModelSerializer):
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)
    etat_libelle = serializers.CharField(source="get_etat_display", read_only=True)
    activite_libelle = serializers.CharField(source="get_activite_display", read_only=True)
    site_nom = serializers.CharField(source="site.nom", read_only=True)
    emplacement_nom = serializers.CharField(source="emplacement.nom", read_only=True, default="")
    ordres_ouverts = serializers.SerializerMethodField()

    class Meta:
        model = Materiel
        fields = ["id", "code", "type", "type_libelle", "designation", "marque", "modele", "numero_serie", "immatriculation",
                  "annee", "capacite", "activite", "activite_libelle", "site", "site_nom", "emplacement", "emplacement_nom",
                  "etat", "etat_libelle", "compteur_heures", "compteur_km", "date_mise_en_service", "observations",
                  "ordres_ouverts"]

    def get_ordres_ouverts(self, obj) -> int:
        return sum(1 for o in obj.ordres.all() if o.ouvert)


class MaterielViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                      mixins.ListModelMixin, viewsets.GenericViewSet):
    """Parc de matériels. Pas de suppression : un matériel sorti du parc passe à l'état réformé."""

    serializer_class = MaterielSerializer
    queryset = Materiel.objects.select_related("site", "emplacement").prefetch_related("ordres")
    filterset_fields = ["type", "etat", "site", "activite", "emplacement"]
    search_fields = ["code", "designation", "marque", "modele", "numero_serie", "immatriculation"]
    ordering_fields = ["code", "designation"]

    perform_create = VueMetier.perform_create
    perform_update = VueMetier.perform_update


class OrdreSerializer(serializers.ModelSerializer):
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)
    materiel_nom = serializers.CharField(source="materiel.__str__", read_only=True)
    materiel_code = serializers.CharField(source="materiel.code", read_only=True)
    site_nom = serializers.CharField(source="materiel.site.nom", read_only=True)
    demandeur_nom = serializers.CharField(source="demandeur.__str__", read_only=True)
    mecanicien_nom = serializers.SerializerMethodField()
    cloture_par_nom = serializers.SerializerMethodField()
    pieces = serializers.SerializerMethodField()
    peut_travailler = serializers.SerializerMethodField()
    peut_piloter = serializers.SerializerMethodField()

    class Meta:
        model = OrdreReparation
        fields = ["id", "numero", "statut", "statut_libelle", "cree_le", "materiel", "materiel_nom", "materiel_code",
                  "site_nom", "type", "type_libelle", "immobilisant", "description", "demandeur_nom", "mecanicien",
                  "mecanicien_nom", "compteur_heures", "compteur_km", "diagnostic", "travaux", "demarre_le", "termine_le",
                  "cloture_par_nom", "cloture_le", "motif_annulation", "pieces", "peut_travailler", "peut_piloter"]
        # Le déroulement passe par les actions du circuit.
        read_only_fields = ["numero", "statut", "mecanicien", "compteur_heures", "compteur_km", "travaux", "demarre_le",
                            "termine_le", "cloture_le", "motif_annulation"]

    def _u(self):
        return self.context["request"].user

    def get_mecanicien_nom(self, obj) -> str:
        return str(obj.mecanicien) if obj.mecanicien_id else ""

    def get_cloture_par_nom(self, obj) -> str:
        return str(obj.cloture_par) if obj.cloture_par_id else ""

    def get_peut_travailler(self, obj) -> bool:
        return obj.peut_travailler(self._u())

    def get_peut_piloter(self, obj) -> bool:
        return obj.pilote(self._u())

    def get_pieces(self, obj) -> list:
        """Pièces sorties du stock pour cet OR. Vide dans les listes, pour ne pas multiplier les requêtes."""
        if self.context["view"].action == "list":
            return []
        lignes = []
        for bon in obj.sorties().prefetch_related("lignes__article__unite").order_by("date", "id"):
            for l in bon.lignes.all():
                lignes.append({"bon": bon.id, "bon_numero": bon.numero, "date": bon.date, "code": l.article.code,
                               "designation": l.article.designation, "quantite": str(l.quantite), "unite": l.article.unite.code})
        return lignes

    def validate_materiel(self, materiel):
        if self.instance and self.instance.materiel_id != materiel.id:
            raise serializers.ValidationError("Le matériel d'un ordre de réparation ne se change pas.")
        if not self.instance and materiel.etat == Materiel.Etat.REFORME:
            raise serializers.ValidationError("Ce matériel est réformé.")
        return materiel

    def validate(self, attrs):
        if self.instance and not self.instance.ouvert:
            raise serializers.ValidationError("Cet ordre de réparation n'est plus ouvert et ne peut plus être modifié.")
        return attrs


class OrdreReparationViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                             mixins.ListModelMixin, viewsets.GenericViewSet):
    """Ordres de réparation. `?ouvert=1` : ceux sur lesquels on peut encore sortir des pièces."""

    serializer_class = OrdreSerializer
    queryset = OrdreReparation.objects.select_related("materiel__site", "demandeur", "mecanicien", "cloture_par")
    filterset_fields = ["statut", "type", "materiel", "mecanicien", "materiel__site"]
    search_fields = ["numero", "description", "materiel__code", "materiel__designation", "materiel__immatriculation"]
    ordering_fields = ["cree_le"]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == "list" and self.request.query_params.get("ouvert"):
            S = OrdreReparation.Statut
            qs = qs.filter(statut__in=[S.OUVERT, S.EN_COURS])
        return qs

    def perform_create(self, serializer):
        u = self.request.user
        serializer.save(demandeur=u, cree_par=u, modifie_par=u)

    def perform_update(self, serializer):
        serializer.save(modifie_par=self.request.user)

    transition = dict(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])

    def _transition(self, request, nom, *args):
        if not request.user.has_perm("technique.view_ordrereparation"):
            raise exceptions.PermissionDenied()
        executer_transition(self.get_object(), nom, request.user, *args)
        return Response(self.get_serializer(self.get_object()).data)

    @action(**transition)
    def affecter(self, request, pk=None):
        try:
            mecanicien = Utilisateur.objects.get(pk=request.data["mecanicien"], is_active=True) if request.data.get("mecanicien") else None
        except (Utilisateur.DoesNotExist, ValueError):
            raise exceptions.ValidationError({"detail": "Mécanicien inconnu."})
        return self._transition(request, "affecter", mecanicien)

    @action(**transition)
    def demarrer(self, request, pk=None):
        d = request.data
        return self._transition(request, "demarrer", str(d.get("diagnostic", "")), _nombre(HEURES, d.get("compteur_heures")),
                                _nombre(KM, d.get("compteur_km")))

    @action(**transition)
    def terminer(self, request, pk=None):
        d = request.data
        return self._transition(request, "terminer", str(d.get("travaux", "")), _nombre(HEURES, d.get("compteur_heures")),
                                _nombre(KM, d.get("compteur_km")))

    @action(**transition)
    def cloturer(self, request, pk=None):
        return self._transition(request, "cloturer")

    @action(**transition)
    def rouvrir(self, request, pk=None):
        return self._transition(request, "rouvrir", str(request.data.get("commentaire", "")))

    @action(**transition)
    def annuler(self, request, pk=None):
        return self._transition(request, "annuler", str(request.data.get("commentaire", "")))
