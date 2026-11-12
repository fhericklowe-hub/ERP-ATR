import datetime
from decimal import Decimal

from django.db import transaction
from django.http import HttpResponse
from rest_framework import exceptions, mixins, permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.achats.views import executer_transition

from .models import Devis, LigneDevis
from .pdf import pdf_devis


class LigneSerializer(serializers.ModelSerializer):
    materiel_nom = serializers.CharField(source="materiel.__str__", read_only=True, default="")
    prix_net = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    montant_ht = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)

    class Meta:
        model = LigneDevis
        fields = ["id", "materiel", "materiel_nom", "designation", "quantite", "prix_unitaire", "remise", "duree",
                  "prix_net", "montant_ht"]
        extra_kwargs = {"quantite": {"min_value": Decimal("0.01")}, "prix_unitaire": {"min_value": 0}, "duree": {"min_value": Decimal("0.01")},
                        "remise": {"min_value": 0, "max_value": 100}}


class DevisSerializer(serializers.ModelSerializer):
    statut_libelle = serializers.SerializerMethodField()
    type_loyer_libelle = serializers.CharField(source="get_type_loyer_display", read_only=True)
    mode_facturation_libelle = serializers.CharField(source="get_mode_facturation_display", read_only=True)
    mode_reglement_libelle = serializers.CharField(source="get_mode_reglement_display", read_only=True)
    activite_libelle = serializers.CharField(source="get_activite_display", read_only=True)
    client_nom = serializers.CharField(source="client.raison_sociale", read_only=True)
    site_nom = serializers.CharField(source="site.nom", read_only=True)
    commercial_nom = serializers.CharField(source="commercial.__str__", read_only=True)
    lignes = LigneSerializer(many=True)
    totaux = serializers.SerializerMethodField()
    expire = serializers.BooleanField(read_only=True)
    peut_agir = serializers.SerializerMethodField()
    peut_gerer = serializers.SerializerMethodField()

    class Meta:
        model = Devis
        fields = ["id", "numero", "statut", "statut_libelle", "expire", "date", "validite", "client", "client_nom", "contact",
                  "libelle", "activite", "activite_libelle", "site", "site_nom", "commercial", "commercial_nom", "type_loyer",
                  "type_loyer_libelle", "date_debut", "date_retour", "lieu", "mode_facturation", "mode_facturation_libelle",
                  "echeance", "mode_reglement", "mode_reglement_libelle", "exonere_tva", "taux_tva", "conditions",
                  "reference_client", "accepte_le", "motif", "lignes", "totaux", "peut_agir", "peut_gerer"]
        read_only_fields = ["commercial"]
        extra_kwargs = {"taux_tva": {"min_value": 0, "max_value": 100}}

    def _u(self):
        return self.context["request"].user

    def get_statut_libelle(self, obj) -> str:
        return "Envoyé, validité dépassée" if obj.expire else obj.get_statut_display()

    def get_totaux(self, obj) -> dict:
        return obj.totaux()

    def get_peut_agir(self, obj) -> bool:
        return obj.peut_agir(self._u())

    def get_peut_gerer(self, obj) -> bool:
        return self._u().has_perm("commercial.gerer_devis")

    def validate_client(self, client):
        if not client.est_client or not client.actif:
            raise serializers.ValidationError("Ce tiers n'est pas un client actif.")
        return client

    def validate(self, attrs):
        d = self.instance
        if d and d.statut != Devis.Statut.BROUILLON:
            raise serializers.ValidationError("Seul un devis en brouillon se modifie. Reprenez-le d'abord.")
        if d and not d.peut_agir(self._u()):
            raise exceptions.PermissionDenied("Ce devis est suivi par un autre commercial.")
        date = attrs.get("date", d.date if d else datetime.date.today())
        validite = attrs.get("validite", d.validite if d else None)
        if validite and validite < date:
            raise serializers.ValidationError({"validite": "La validité ne peut pas précéder la date du devis."})
        debut, retour = attrs.get("date_debut", d.date_debut if d else None), attrs.get("date_retour", d.date_retour if d else None)
        if debut and retour and retour.date() < debut:
            raise serializers.ValidationError({"date_retour": "Le retour ne peut pas précéder le début."})
        return attrs

    def _ecrire_lignes(self, devis, lignes):
        devis.lignes.all().delete()
        LigneDevis.objects.bulk_create([LigneDevis(devis=devis, **l) for l in lignes])

    @transaction.atomic
    def create(self, validated_data):
        lignes = validated_data.pop("lignes", [])
        devis = Devis.objects.create(**validated_data)
        self._ecrire_lignes(devis, lignes)
        return devis

    @transaction.atomic
    def update(self, instance, validated_data):
        lignes = validated_data.pop("lignes", None)
        instance = super().update(instance, validated_data)
        if lignes is not None:
            self._ecrire_lignes(instance, lignes)
        return instance


class DevisViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, mixins.ListModelMixin,
                   viewsets.GenericViewSet):
    """Devis de location. Pas de suppression : un devis abandonné s'annule, avec son motif."""

    serializer_class = DevisSerializer
    queryset = Devis.objects.select_related("client", "site", "commercial").prefetch_related("lignes__materiel")
    filterset_fields = ["statut", "client", "commercial", "site", "activite"]
    search_fields = ["numero", "libelle", "client__raison_sociale", "reference_client"]
    ordering_fields = ["cree_le", "date"]

    def perform_create(self, serializer):
        u = self.request.user
        serializer.save(commercial=u, cree_par=u, modifie_par=u)

    def perform_update(self, serializer):
        serializer.save(modifie_par=self.request.user)

    transition = dict(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])

    def _transition(self, request, nom, *args):
        if not request.user.has_perm("commercial.view_devis"):
            raise exceptions.PermissionDenied()
        executer_transition(self.get_object(), nom, request.user, *args)
        return Response(self.get_serializer(self.get_object()).data)

    @action(**transition)
    def envoyer(self, request, pk=None):
        return self._transition(request, "envoyer")

    @action(**transition)
    def reprendre(self, request, pk=None):
        return self._transition(request, "reprendre")

    @action(**transition)
    def accepter(self, request, pk=None):
        try:
            jour = datetime.date.fromisoformat(request.data["accepte_le"]) if request.data.get("accepte_le") else None
        except (TypeError, ValueError):
            raise exceptions.ValidationError({"detail": "Date invalide."})
        return self._transition(request, "accepter", str(request.data.get("reference_client", "")), jour)

    @action(**transition)
    def refuser(self, request, pk=None):
        return self._transition(request, "refuser", str(request.data.get("motif", "")))

    @action(**transition)
    def annuler(self, request, pk=None):
        return self._transition(request, "annuler", str(request.data.get("motif", "")))

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        """PDF du devis d'après le modèle de l'entreprise, suivi des conditions générales de location."""
        devis = self.get_object()
        reponse = HttpResponse(pdf_devis(devis), content_type="application/pdf")
        reponse["Content-Disposition"] = f'inline; filename="{devis.numero}.pdf"'
        return reponse
