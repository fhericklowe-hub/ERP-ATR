from django.db import transaction
from django.http import HttpResponse
from rest_framework import exceptions, mixins, permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .commande import BonCommande
from .pdf import pdf_bon_reception
from .reception import BonReception, LigneBonReception
from .views import executer_transition


class LigneReceptionSerializer(serializers.ModelSerializer):
    reference = serializers.CharField(source="ligne_commande.reference", read_only=True)
    designation = serializers.CharField(source="ligne_commande.designation", read_only=True)
    quantite_commandee = serializers.DecimalField(source="ligne_commande.quantite", max_digits=12, decimal_places=2,
                                                  read_only=True)
    montant_ht = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = LigneBonReception
        fields = ["id", "ligne_commande", "reference", "designation", "quantite_commandee", "quantite_recue",
                  "quantite_stock", "numero_materiel", "numero_serie", "immatriculation", "observations", "montant_ht"]


class BonReceptionSerializer(serializers.ModelSerializer):
    lignes = LigneReceptionSerializer(many=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    commande_numero = serializers.CharField(source="commande.numero", read_only=True)
    fournisseur_nom = serializers.CharField(source="commande.fournisseur.raison_sociale", read_only=True)
    site_nom = serializers.CharField(source="commande.site.nom", read_only=True)
    service_nom = serializers.CharField(source="commande.service.nom", read_only=True)
    objet = serializers.CharField(source="commande.objet", read_only=True)
    devise = serializers.CharField(source="commande.devise", read_only=True)
    receptionnaire_nom = serializers.CharField(source="receptionnaire.__str__", read_only=True)
    annule_par_nom = serializers.SerializerMethodField()
    total_ht = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    modifiable = serializers.BooleanField(read_only=True)
    peut_preparer = serializers.SerializerMethodField()
    peut_annuler = serializers.SerializerMethodField()

    class Meta:
        model = BonReception
        fields = [
            "id", "numero", "ancien_numero", "statut", "statut_libelle", "date", "commande", "commande_numero",
            "fournisseur_nom", "site_nom", "service_nom", "objet", "devise", "numero_livraison", "receptionnaire",
            "receptionnaire_nom", "observations", "valide_le", "annule_par_nom", "annule_le", "motif_annulation",
            "total_ht", "modifiable", "peut_preparer", "peut_annuler", "lignes",
        ]
        read_only_fields = ["numero", "statut", "receptionnaire", "valide_le", "annule_le", "motif_annulation"]

    def _utilisateur(self):
        return self.context["request"].user

    def get_annule_par_nom(self, obj) -> str:
        return str(obj.annule_par) if obj.annule_par_id else ""

    def get_peut_preparer(self, obj) -> bool:
        return obj.peut_preparer(self._utilisateur())

    def get_peut_annuler(self, obj) -> bool:
        return obj.peut_annuler(self._utilisateur())

    def validate_commande(self, commande):
        if self.instance and self.instance.commande_id != commande.id:
            raise serializers.ValidationError("Le bon de commande d'un bon de réception ne peut pas être changé.")
        if not self.instance and commande.statut != BonCommande.Statut.TRANSMIS:
            raise serializers.ValidationError("La réception se fait sur un bon de commande transmis au fournisseur.")
        return commande

    def validate(self, attrs):
        if self.instance and not self.instance.modifiable and set(attrs) - {"ancien_numero"}:
            raise serializers.ValidationError("Ce bon de réception est validé et ne peut plus être modifié.")
        commande = attrs.get("commande") or (self.instance and self.instance.commande)
        vues = set()
        for l in attrs.get("lignes", []):
            lc = l["ligne_commande"]
            if lc.bon_id != commande.id:
                raise serializers.ValidationError("Une ligne ne correspond pas à ce bon de commande.")
            if lc.id in vues:
                raise serializers.ValidationError(f"« {lc.designation} » figure deux fois.")
            vues.add(lc.id)
            if l["quantite_recue"] <= 0:
                raise serializers.ValidationError(f"« {lc.designation} » : la quantité reçue doit être positive.")
            if not 0 <= l.get("quantite_stock", 0) <= l["quantite_recue"]:
                raise serializers.ValidationError(
                    f"« {lc.designation} » : la quantité à mettre en stock ne peut pas dépasser la quantité reçue."
                )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        lignes = validated_data.pop("lignes", [])
        bon = BonReception.objects.create(**validated_data)
        LigneBonReception.objects.bulk_create(LigneBonReception(bon=bon, **l) for l in lignes)
        return bon

    @transaction.atomic
    def update(self, instance, validated_data):
        lignes = validated_data.pop("lignes", None)
        instance = super().update(instance, validated_data)
        if lignes is not None:
            instance.lignes.all().delete()
            LigneBonReception.objects.bulk_create(LigneBonReception(bon=instance, **l) for l in lignes)
        return instance


class BonReceptionViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                          mixins.ListModelMixin, viewsets.GenericViewSet):
    """Bons de réception. Pas de suppression : une réception se corrige en brouillon ou s'annule."""

    serializer_class = BonReceptionSerializer
    queryset = BonReception.objects.select_related(
        "commande__fournisseur", "commande__site", "commande__service", "receptionnaire", "annule_par"
    ).prefetch_related("lignes__ligne_commande")
    filterset_fields = ["statut", "commande", "commande__fournisseur", "commande__site", "receptionnaire"]
    search_fields = ["numero", "ancien_numero", "numero_livraison", "commande__numero",
                     "commande__fournisseur__raison_sociale", "lignes__numero_materiel", "lignes__numero_serie", "lignes__immatriculation"]
    ordering_fields = ["cree_le", "date"]

    def perform_create(self, serializer):
        u = self.request.user
        serializer.save(receptionnaire=u, cree_par=u, modifie_par=u)

    def update(self, request, *args, **kwargs):
        if not self.get_object().peut_preparer(request.user):
            raise exceptions.PermissionDenied("Seul le réceptionnaire ou le responsable achats peut modifier ce bon.")
        return super().update(request, *args, **kwargs)

    def perform_update(self, serializer):
        serializer.save(modifie_par=self.request.user)

    transition = dict(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])

    def _transition(self, request, nom, *args):
        executer_transition(self.get_object(), nom, request.user, *args)
        return Response(self.get_serializer(self.get_object()).data)

    @action(**transition)
    def valider(self, request, pk=None):
        return self._transition(request, "valider")

    @action(**transition)
    def annuler(self, request, pk=None):
        return self._transition(request, "annuler", request.data.get("commentaire", ""))

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        bon = self.get_object()
        reponse = HttpResponse(pdf_bon_reception(bon), content_type="application/pdf")
        reponse["Content-Disposition"] = f'inline; filename="{bon.numero}.pdf"'
        return reponse
