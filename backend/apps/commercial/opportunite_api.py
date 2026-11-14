from rest_framework import exceptions, mixins, permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.achats.views import executer_transition
from apps.core.export import ExportExcel

from .opportunite import DecisionOpportunite, Opportunite


class DecisionSerializer(serializers.ModelSerializer):
    auteur_nom = serializers.CharField(source="auteur.__str__", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    niveau_libelle = serializers.SerializerMethodField()

    class Meta:
        model = DecisionOpportunite
        fields = ["id", "date", "auteur_nom", "action", "niveau", "niveau_libelle", "commentaire", "statut", "statut_libelle"]

    def get_niveau_libelle(self, d) -> str:
        return {"ATT_RESP": "Responsable commercial", "ATT_FIN": "Finance", "ATT_DG": "DG"}.get(d.niveau, "")


class OpportuniteSerializer(serializers.ModelSerializer):
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    type_affaire_libelle = serializers.CharField(source="get_type_affaire_display", read_only=True)
    origine_libelle = serializers.CharField(source="get_origine_display", read_only=True)
    phase_libelle = serializers.CharField(source="get_phase_display", read_only=True)
    activite_libelle = serializers.CharField(source="get_activite_display", read_only=True)
    client_nom = serializers.CharField(source="client.raison_sociale", read_only=True)
    site_nom = serializers.CharField(source="site.nom", read_only=True)
    commercial_nom = serializers.CharField(source="commercial.__str__", read_only=True)
    taux_marge = serializers.DecimalField(max_digits=6, decimal_places=1, read_only=True)
    decisions = DecisionSerializer(many=True, read_only=True)
    devis = serializers.SerializerMethodField()
    modifiable = serializers.BooleanField(read_only=True)
    peut_preparer = serializers.SerializerMethodField()
    peut_decider = serializers.SerializerMethodField()
    peut_annuler = serializers.SerializerMethodField()

    class Meta:
        model = Opportunite
        fields = [
            "id", "numero", "statut", "statut_libelle", "nom_affaire", "client", "client_nom", "site", "site_nom", "commercial",
            "commercial_nom", "activite", "activite_libelle", "type_affaire", "type_affaire_libelle", "origine", "origine_libelle",
            "phase", "phase_libelle", "probabilite", "devise", "ca_previsionnel", "marge_previsionnelle", "taux_marge", "ca_services",
            "marge_services", "ca_materiel", "marge_materiel", "lieu", "date_prise_commande", "prochaine_etape", "reference_ao",
            "date_lancement_ao", "date_limite_ao", "partenaire", "part_partenaire", "risques", "observations", "decisions", "devis",
            "modifiable", "peut_preparer", "peut_decider", "peut_annuler",
        ]
        read_only_fields = ["commercial"]
        extra_kwargs = {"probabilite": {"min_value": 0, "max_value": 100}, "part_partenaire": {"min_value": 0, "max_value": 100},
                        "ca_previsionnel": {"min_value": 0}}

    def _u(self):
        return self.context["request"].user

    def get_devis(self, o) -> list:
        return [{"id": d.id, "numero": d.numero, "statut": d.statut, "statut_libelle": d.get_statut_display()} for d in o.devis.all()]

    def get_peut_preparer(self, o) -> bool:
        return o.peut_preparer(self._u())

    def get_peut_decider(self, o) -> bool:
        return o.peut_decider(self._u())

    def get_peut_annuler(self, o) -> bool:
        return o.statut not in (o.Statut.NO_GO, o.Statut.ANNULEE) and o.peut_preparer(self._u())

    def validate_client(self, client):
        if not client.est_client or not client.actif:
            raise serializers.ValidationError("Ce tiers n'est pas un client actif.")
        return client

    def validate(self, attrs):
        o = self.instance
        if o and o.statut != Opportunite.Statut.BROUILLON:
            raise serializers.ValidationError("Seule une fiche en brouillon se modifie.")
        if o and not o.peut_preparer(self._u()):
            raise exceptions.PermissionDenied("Cette fiche est suivie par un autre commercial.")
        ca = attrs.get("ca_previsionnel", o.ca_previsionnel if o else None)
        marge = attrs.get("marge_previsionnelle", o.marge_previsionnelle if o else None)
        if ca is not None and marge is not None and marge > ca:
            raise serializers.ValidationError({"marge_previsionnelle": "La marge ne peut pas dépasser le chiffre d'affaires."})
        debut, fin = attrs.get("date_lancement_ao", o.date_lancement_ao if o else None), attrs.get("date_limite_ao", o.date_limite_ao if o else None)
        if debut and fin and fin < debut:
            raise serializers.ValidationError({"date_limite_ao": "La date limite ne peut pas précéder le lancement."})
        return attrs


class OpportuniteViewSet(ExportExcel, mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                         mixins.ListModelMixin, viewsets.GenericViewSet):
    """Fiches GO / NO GO. Pas de suppression : une fiche abandonnée s'annule, avec son motif."""

    serializer_class = OpportuniteSerializer
    queryset = Opportunite.objects.select_related("client", "site", "commercial").prefetch_related("decisions__auteur", "devis")
    filterset_fields = ["statut", "client", "commercial", "site", "activite", "type_affaire"]
    search_fields = ["numero", "nom_affaire", "client__raison_sociale", "reference_ao"]
    ordering_fields = ["cree_le", "ca_previsionnel"]
    export_titre, export_fichier = "Fiches GO - NO GO", "go-no-go"
    export_colonnes = [
        ("N°", "numero"), ("Affaire", "nom_affaire"), ("Client", "client_nom"), ("Agence", "site_nom"), ("Commercial", "commercial_nom"),
        ("Statut", "statut_libelle"), ("Type", "type_affaire_libelle"), ("Origine", "origine_libelle"), ("Phase", "phase_libelle"),
        ("Probabilité (%)", "probabilite", "nombre"), ("Devise", "devise"), ("CA prévisionnel", "ca_previsionnel", "nombre"),
        ("Marge prévisionnelle", "marge_previsionnelle", "nombre"), ("Taux de marge (%)", "taux_marge", "nombre"),
        ("Prise de commande prévue", "date_prise_commande", "date"),
    ]

    def perform_create(self, serializer):
        u = self.request.user
        serializer.save(commercial=u, cree_par=u, modifie_par=u)

    def perform_update(self, serializer):
        serializer.save(modifie_par=self.request.user)

    transition = dict(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])

    def _transition(self, request, nom, *args):
        if not request.user.has_perm("commercial.view_opportunite"):
            raise exceptions.PermissionDenied()
        executer_transition(self.get_object(), nom, request.user, *args)
        return Response(self.get_serializer(self.get_object()).data)

    @action(**transition)
    def soumettre(self, request, pk=None):
        return self._transition(request, "soumettre")

    @action(**transition)
    def valider(self, request, pk=None):
        return self._transition(request, "valider", str(request.data.get("commentaire", "")))

    @action(**transition)
    def refuser(self, request, pk=None):
        return self._transition(request, "refuser", str(request.data.get("commentaire", "")))

    @action(**transition)
    def renvoyer(self, request, pk=None):
        return self._transition(request, "renvoyer", str(request.data.get("commentaire", "")))

    @action(**transition)
    def annuler(self, request, pk=None):
        return self._transition(request, "annuler", str(request.data.get("commentaire", "")))
