from django.db import transaction
from django.http import HttpResponse
from rest_framework import exceptions, mixins, permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .commande import BonCommande, EvenementCommande, LigneBonCommande
from .models import DemandeAchat
from .pdf import pdf_bon_commande
from .views import executer_transition


class LigneCommandeSerializer(serializers.ModelSerializer):
    prix_net = serializers.DecimalField(max_digits=14, decimal_places=0, read_only=True)
    montant_ht = serializers.DecimalField(max_digits=14, decimal_places=0, read_only=True)

    quantite_recue = serializers.SerializerMethodField()

    class Meta:
        model = LigneBonCommande
        fields = ["id", "article", "reference", "designation", "quantite", "prix_unitaire", "remise", "taux_tva",
                  "prix_net", "montant_ht", "quantite_recue"]

    def get_quantite_recue(self, obj) -> str:
        return str(self.context.get("recues", {}).get(obj.id, 0))


class EvenementCommandeSerializer(serializers.ModelSerializer):
    auteur_nom = serializers.CharField(source="auteur.__str__", read_only=True)
    action_libelle = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = EvenementCommande
        fields = ["id", "action", "action_libelle", "statut", "auteur_nom", "date", "commentaire"]


class BonCommandeSerializer(serializers.ModelSerializer):
    lignes = LigneCommandeSerializer(many=True)
    evenements = EvenementCommandeSerializer(many=True, read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    mode_reglement_libelle = serializers.CharField(source="get_mode_reglement_display", read_only=True)
    demande_numero = serializers.CharField(source="demande.numero", read_only=True)
    fournisseur_nom = serializers.CharField(source="fournisseur.raison_sociale", read_only=True)
    acheteur_nom = serializers.CharField(source="acheteur.__str__", read_only=True)
    site_nom = serializers.CharField(source="site.nom", read_only=True)
    service_nom = serializers.CharField(source="service.nom", read_only=True)
    totaux = serializers.SerializerMethodField()
    modifiable = serializers.BooleanField(read_only=True)
    definitif = serializers.BooleanField(read_only=True)
    peut_valider = serializers.SerializerMethodField()
    peut_preparer = serializers.SerializerMethodField()
    peut_annuler = serializers.SerializerMethodField()
    etat_reception = serializers.CharField(read_only=True)
    etat_reception_libelle = serializers.CharField(source="get_etat_reception_display", read_only=True)
    receptions = serializers.SerializerMethodField()

    class Meta:
        model = BonCommande
        fields = [
            "id", "numero", "ancien_numero", "statut", "statut_libelle", "date", "demande", "demande_numero",
            "fournisseur", "fournisseur_nom", "reference_fournisseur", "objet", "site", "site_nom",
            "service", "service_nom", "acheteur", "acheteur_nom", "date_livraison", "transport",
            "adresse_livraison", "echeance", "mode_reglement", "mode_reglement_libelle", "transmis_le", "totaux",
            "modifiable", "definitif", "peut_valider", "peut_preparer", "peut_annuler", "etat_reception",
            "etat_reception_libelle", "receptions", "lignes", "evenements",
        ]
        read_only_fields = ["numero", "statut", "acheteur", "transmis_le"]

    def _utilisateur(self):
        return self.context["request"].user

    def to_representation(self, obj):
        self.context["recues"] = obj.quantites_recues()
        return super().to_representation(obj)

    def get_receptions(self, obj) -> list:
        return [{"id": r.id, "numero": r.numero, "date": r.date, "statut": r.statut,
                 "statut_libelle": r.get_statut_display(), "numero_livraison": r.numero_livraison}
                for r in obj.receptions.all()]

    def get_totaux(self, obj) -> dict:
        return obj.totaux()

    def get_peut_valider(self, obj) -> bool:
        return obj.peut_valider(self._utilisateur())

    def get_peut_preparer(self, obj) -> bool:
        return obj.peut_preparer(self._utilisateur())

    def get_peut_annuler(self, obj) -> bool:
        return obj.statut != obj.Statut.ANNULE and self._utilisateur().has_perm("achats.valider_responsable_boncommande")

    def validate_demande(self, demande):
        if self.instance and self.instance.demande_id != demande.id:
            raise serializers.ValidationError("La demande d'achat d'un bon de commande ne peut pas être changée.")
        if not self.instance and demande.statut != DemandeAchat.Statut.VALIDEE:
            raise serializers.ValidationError("Le bon de commande se crée à partir d'une demande d'achat validée.")
        return demande

    def validate_fournisseur(self, fournisseur):
        if not fournisseur.est_fournisseur or not fournisseur.actif:
            raise serializers.ValidationError("Ce tiers n'est pas un fournisseur actif.")
        return fournisseur

    def validate(self, attrs):
        if self.instance and not self.instance.modifiable and set(attrs) - {"ancien_numero"}:
            raise serializers.ValidationError("Ce bon de commande a été soumis et ne peut plus être modifié.")
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        lignes = validated_data.pop("lignes", [])
        bon = BonCommande.objects.create(**validated_data)
        LigneBonCommande.objects.bulk_create(LigneBonCommande(bon=bon, **l) for l in lignes)
        return bon

    @transaction.atomic
    def update(self, instance, validated_data):
        lignes = validated_data.pop("lignes", None)
        instance = super().update(instance, validated_data)
        if lignes is not None:
            instance.lignes.all().delete()
            LigneBonCommande.objects.bulk_create(LigneBonCommande(bon=instance, **l) for l in lignes)
        return instance


class BonCommandeViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                         mixins.ListModelMixin, viewsets.GenericViewSet):
    """Bons de commande. Pas de suppression : un bon se corrige ou s'annule."""

    serializer_class = BonCommandeSerializer
    queryset = BonCommande.objects.select_related("demande", "fournisseur", "site", "service", "acheteur").prefetch_related(
        "lignes", "evenements__auteur", "receptions"
    )
    filterset_fields = ["statut", "fournisseur", "site", "service", "acheteur", "demande"]
    search_fields = ["numero", "ancien_numero", "objet", "reference_fournisseur", "fournisseur__raison_sociale",
                     "demande__numero"]
    ordering_fields = ["cree_le", "date", "date_livraison"]

    def perform_create(self, serializer):
        u = self.request.user
        serializer.save(acheteur=u, cree_par=u, modifie_par=u)

    def update(self, request, *args, **kwargs):
        if not self.get_object().peut_preparer(request.user):
            raise exceptions.PermissionDenied("Seul l'acheteur du bon ou le responsable achats peut le modifier.")
        return super().update(request, *args, **kwargs)

    def perform_update(self, serializer):
        serializer.save(modifie_par=self.request.user)

    transition = dict(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])

    def _transition(self, request, nom, *args):
        executer_transition(self.get_object(), nom, request.user, *args)
        return Response(self.get_serializer(self.get_object()).data)

    @action(**transition)
    def soumettre(self, request, pk=None):
        return self._transition(request, "soumettre")

    @action(**transition)
    def valider(self, request, pk=None):
        return self._transition(request, "valider", request.data.get("commentaire", ""))

    @action(**transition)
    def refuser(self, request, pk=None):
        return self._transition(request, "refuser", request.data.get("commentaire", ""))

    @action(**transition)
    def transmettre(self, request, pk=None):
        return self._transition(request, "transmettre")

    @action(**transition)
    def cloturer(self, request, pk=None):
        return self._transition(request, "cloturer", request.data.get("commentaire", ""))

    @action(**transition)
    def decloturer(self, request, pk=None):
        return self._transition(request, "decloturer", request.data.get("commentaire", ""))

    @action(**transition)
    def annuler(self, request, pk=None):
        return self._transition(request, "annuler", request.data.get("commentaire", ""))

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        """PDF du bon. Tant qu'il n'a pas ses deux validations, il porte la mention PROJET."""
        bon = self.get_object()
        reponse = HttpResponse(pdf_bon_commande(bon), content_type="application/pdf")
        reponse["Content-Disposition"] = f'inline; filename="{bon.numero}.pdf"'
        return reponse
