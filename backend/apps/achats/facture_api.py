from datetime import date

from django.core.exceptions import ValidationError as ErreurDjango
from rest_framework import exceptions, mixins, permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.export import ExportExcel

from .commande import BonCommande
from .facture import FactureFournisseur
from .views import executer_transition


class FactureSerializer(serializers.ModelSerializer):
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    commande_numero = serializers.CharField(source="commande.numero", read_only=True)
    commande_objet = serializers.CharField(source="commande.objet", read_only=True)
    fournisseur = serializers.IntegerField(source="commande.fournisseur_id", read_only=True)
    fournisseur_nom = serializers.CharField(source="commande.fournisseur.raison_sociale", read_only=True)
    devise = serializers.CharField(source="commande.devise", read_only=True)
    bon_a_payer_par_nom = serializers.SerializerMethodField()
    rapprochement = serializers.SerializerMethodField()
    modifiable = serializers.BooleanField(read_only=True)
    peut_bon_a_payer = serializers.SerializerMethodField()
    peut_payer = serializers.SerializerMethodField()
    peut_annuler = serializers.SerializerMethodField()
    en_retard = serializers.SerializerMethodField()

    class Meta:
        model = FactureFournisseur
        fields = [
            "id", "numero", "numero_facture", "statut", "statut_libelle", "commande", "commande_numero", "commande_objet",
            "fournisseur", "fournisseur_nom", "devise", "date_facture", "date_echeance", "montant_ht", "montant_ttc", "observations",
            "commentaire_ecart", "bon_a_payer_par_nom", "bon_a_payer_le", "payee_le", "reference_paiement", "motif_annulation",
            "rapprochement", "modifiable", "peut_bon_a_payer", "peut_payer", "peut_annuler", "en_retard",
        ]
        read_only_fields = ["numero", "statut", "commentaire_ecart", "bon_a_payer_le", "payee_le", "reference_paiement", "motif_annulation"]

    def _u(self):
        return self.context["request"].user

    def get_bon_a_payer_par_nom(self, f) -> str:
        return str(f.bon_a_payer_par) if f.bon_a_payer_par_id else ""

    def get_rapprochement(self, f) -> dict:
        return f.rapprochement()

    def get_peut_bon_a_payer(self, f) -> bool:
        return f.statut == f.Statut.A_VERIFIER and self._u().has_perm("achats.donner_bon_a_payer_facturefournisseur")

    def get_peut_payer(self, f) -> bool:
        return f.statut == f.Statut.BON_A_PAYER and self._u().has_perm("achats.payer_facturefournisseur")

    def get_peut_annuler(self, f) -> bool:
        return f.statut in (f.Statut.A_VERIFIER, f.Statut.BON_A_PAYER) and (
            self._u().has_perm("achats.donner_bon_a_payer_facturefournisseur") or (f.modifiable and self._u().has_perm("achats.change_facturefournisseur")))

    def get_en_retard(self, f) -> bool:
        return bool(f.date_echeance and f.statut in (f.Statut.A_VERIFIER, f.Statut.BON_A_PAYER) and f.date_echeance < date.today())

    def validate_commande(self, commande):
        if self.instance and self.instance.commande_id != commande.id:
            raise serializers.ValidationError("Le bon de commande d'une facture ne peut pas être changé.")
        if not self.instance and commande.statut not in (BonCommande.Statut.TRANSMIS, BonCommande.Statut.CLOTURE):
            raise serializers.ValidationError("Une facture se rattache à un bon de commande transmis au fournisseur ou clôturé.")
        return commande

    def validate(self, attrs):
        if self.instance and not self.instance.modifiable and set(attrs):
            raise serializers.ValidationError("Cette facture n'est plus à vérifier : elle ne peut plus être modifiée.")
        ht = attrs.get("montant_ht", self.instance.montant_ht if self.instance else None)
        ttc = attrs.get("montant_ttc", self.instance.montant_ttc if self.instance else None)
        if ht is not None and ht <= 0:
            raise serializers.ValidationError("Le montant HT doit être positif.")
        if ht is not None and ttc is not None and ttc < ht:
            raise serializers.ValidationError("Le montant TTC ne peut pas être inférieur au montant HT.")
        commande = attrs.get("commande") or (self.instance and self.instance.commande)
        numero = (attrs.get("numero_facture") or (self.instance and self.instance.numero_facture) or "").strip()
        attrs["numero_facture"] = numero
        doublon = FactureFournisseur.objects.filter(commande__fournisseur=commande.fournisseur_id, numero_facture__iexact=numero).exclude(statut="ANNULEE")
        if self.instance:
            doublon = doublon.exclude(pk=self.instance.pk)
        if doublon.exists():
            raise serializers.ValidationError(f"La facture n° {numero} de ce fournisseur est déjà enregistrée ({doublon.first().numero}).")
        return attrs


class FactureViewSet(ExportExcel, mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                     mixins.ListModelMixin, viewsets.GenericViewSet):
    """Factures fournisseurs. Pas de suppression : une facture erronée s'annule avec un motif."""

    serializer_class = FactureSerializer
    queryset = FactureFournisseur.objects.select_related("commande__fournisseur", "bon_a_payer_par")
    filterset_fields = ["statut", "commande", "commande__fournisseur"]
    search_fields = ["numero", "numero_facture", "commande__numero", "commande__fournisseur__raison_sociale"]
    ordering_fields = ["date_facture", "date_echeance", "cree_le"]
    export_titre, export_fichier = "Factures fournisseurs", "factures-fournisseurs"
    export_colonnes = [
        ("N°", "numero"), ("N° facture fournisseur", "numero_facture"), ("Date", "date_facture", "date"), ("Échéance", "date_echeance", "date"),
        ("Statut", "statut_libelle"), ("Fournisseur", "fournisseur_nom"), ("Bon de commande", "commande_numero"), ("Devise", "devise"),
        ("Montant HT", "montant_ht", "nombre"), ("Montant TTC", "montant_ttc", "nombre"),
        ("Écart avec les réceptions (HT)", "rapprochement.ecart_ht", "nombre"), ("Payée le", "payee_le", "date"), ("Référence du paiement", "reference_paiement"),
    ]

    def perform_create(self, serializer):
        serializer.save(cree_par=self.request.user, modifie_par=self.request.user)

    def perform_update(self, serializer):
        serializer.save(modifie_par=self.request.user)

    transition = dict(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])

    def _transition(self, request, nom, *args):
        executer_transition(self.get_object(), nom, request.user, *args)
        return Response(self.get_serializer(self.get_object()).data)

    @action(**transition)
    def bon_a_payer(self, request, pk=None):
        return self._transition(request, "donner_bon_a_payer", request.data.get("commentaire", ""))

    @action(**transition)
    def payer(self, request, pk=None):
        brut = request.data.get("date")
        try:
            jour = date.fromisoformat(brut) if brut else None
        except ValueError:
            raise exceptions.ValidationError({"detail": ["Date de paiement invalide."]})
        return self._transition(request, "payer", jour, request.data.get("reference", ""))

    @action(**transition)
    def annuler(self, request, pk=None):
        return self._transition(request, "annuler", request.data.get("commentaire", ""))
