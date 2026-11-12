from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from rest_framework import exceptions, mixins, permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .budget import DemandeBudget, DevisDemande, EvenementBudget, LigneBudgetaire
from .pdf_budget import pdf_demande_budget
from .views import executer_transition

# Ce que chaque acteur peut modifier, selon l'étape.
CHAMPS_DEMANDEUR = {
    "type", "date", "fast_track", "service", "site", "activite", "activite_autre", "projet", "intitule", "description",
    "prevu_budget", "ligne_budgetaire", "motif_hors_budget", "nature", "motif_investissement", "numero_contrat",
    "client", "loyer_mensuel", "ancien_numero",
}
CHAMPS_ACHATS = {"devis", "critere_qualite", "critere_delai", "critere_prix", "critere_autre", "justification_devis"}
CHAMPS_CONTROLE = {"service_impute", "compte", "ligne_budgetaire", "prevu_budget", "motif_hors_budget", "duree_amortissement"}


class LigneBudgetaireSerializer(serializers.ModelSerializer):
    service_nom = serializers.CharField(source="service.nom", read_only=True)
    engage = serializers.SerializerMethodField()
    disponible = serializers.SerializerMethodField()

    class Meta:
        model = LigneBudgetaire
        fields = ["id", "exercice", "service", "service_nom", "intitule", "compte", "montant", "actif", "engage", "disponible"]

    def get_engage(self, obj) -> str:
        return str(obj.engage())

    def get_disponible(self, obj) -> str:
        return str(obj.disponible())


class LigneBudgetaireViewSet(viewsets.ModelViewSet):
    """Lignes budgétaires, tenues par le contrôle de gestion."""

    serializer_class = LigneBudgetaireSerializer
    queryset = LigneBudgetaire.objects.select_related("service")
    filterset_fields = ["exercice", "service", "actif"]
    search_fields = ["intitule"]
    pagination_class = None

    def perform_create(self, serializer):
        serializer.save(cree_par=self.request.user, modifie_par=self.request.user)

    def perform_update(self, serializer):
        serializer.save(modifie_par=self.request.user)


class DevisSerializer(serializers.ModelSerializer):
    fournisseur_nom = serializers.CharField(source="fournisseur.raison_sociale", read_only=True)

    class Meta:
        model = DevisDemande
        fields = ["id", "fournisseur", "fournisseur_nom", "numero", "date", "montant", "retenu"]

    def validate_fournisseur(self, fournisseur):
        if not fournisseur.est_fournisseur or not fournisseur.actif:
            raise serializers.ValidationError("Ce tiers n'est pas un fournisseur actif.")
        return fournisseur


class EvenementBudgetSerializer(serializers.ModelSerializer):
    auteur_nom = serializers.CharField(source="auteur.__str__", read_only=True)
    action_libelle = serializers.CharField(source="get_action_display", read_only=True)
    etape_libelle = serializers.CharField(source="get_etape_display", read_only=True)

    class Meta:
        model = EvenementBudget
        fields = ["id", "action", "action_libelle", "etape", "etape_libelle", "statut", "auteur_nom", "date", "commentaire"]


class DemandeBudgetSerializer(serializers.ModelSerializer):
    devis = DevisSerializer(many=True, required=False)
    evenements = EvenementBudgetSerializer(many=True, read_only=True)
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    nature_libelle = serializers.CharField(source="get_nature_display", read_only=True)
    motif_investissement_libelle = serializers.CharField(source="get_motif_investissement_display", read_only=True)
    activite_libelle = serializers.CharField(read_only=True)
    demandeur_nom = serializers.CharField(source="demandeur.__str__", read_only=True)
    demandeur_fonction = serializers.CharField(source="demandeur.fonction", read_only=True)
    acheteur_nom = serializers.SerializerMethodField()
    service_nom = serializers.CharField(source="service.nom", read_only=True)
    site_nom = serializers.CharField(source="site.nom", read_only=True)
    projet_nom = serializers.CharField(source="projet.nom", read_only=True, default="")
    code_analytique = serializers.CharField(source="projet.code_analytique", read_only=True, default="")
    client_nom = serializers.CharField(source="client.raison_sociale", read_only=True, default="")
    ligne_budgetaire_nom = serializers.SerializerMethodField()
    service_impute_nom = serializers.CharField(source="service_impute.nom", read_only=True, default="")
    compte_nom = serializers.SerializerMethodField()
    article_ng = serializers.CharField(source="compte.article_ng", read_only=True, default="")
    situation_budget = serializers.SerializerMethodField()
    motifs_dg = serializers.SerializerMethodField()
    signatures = serializers.SerializerMethodField()
    bons_commande = serializers.SerializerMethodField()
    est_investissement = serializers.BooleanField(read_only=True)
    accord_dg_requis = serializers.BooleanField(read_only=True)
    modifiable = serializers.SerializerMethodField()
    peut_valider = serializers.SerializerMethodField()
    peut_consulter = serializers.SerializerMethodField()
    peut_imputer = serializers.SerializerMethodField()
    peut_commander = serializers.SerializerMethodField()

    class Meta:
        model = DemandeBudget
        fields = [
            "id", "type", "type_libelle", "numero", "ancien_numero", "statut", "statut_libelle", "date", "fast_track",
            "demandeur", "demandeur_nom", "demandeur_fonction", "service", "service_nom", "site", "site_nom",
            "activite", "activite_autre", "activite_libelle", "projet", "projet_nom", "code_analytique",
            "intitule", "description", "prevu_budget", "ligne_budgetaire", "ligne_budgetaire_nom", "motif_hors_budget",
            "nature", "nature_libelle", "motif_investissement", "motif_investissement_libelle", "numero_contrat",
            "client", "client_nom", "loyer_mensuel", "duree_amortissement", "acheteur", "acheteur_nom",
            "critere_qualite", "critere_delai", "critere_prix", "critere_autre", "justification_devis", "montant",
            "service_impute", "service_impute_nom", "compte", "compte_nom", "article_ng", "situation_budget",
            "motifs_dg", "signatures", "bons_commande", "est_investissement", "accord_dg_requis", "modifiable",
            "peut_valider", "peut_consulter", "peut_imputer", "peut_commander", "devis", "evenements",
        ]
        read_only_fields = ["numero", "statut", "demandeur", "acheteur", "montant"]

    def _utilisateur(self):
        return self.context["request"].user

    def get_ligne_budgetaire_nom(self, obj) -> str:
        return str(obj.ligne_budgetaire) if obj.ligne_budgetaire_id else ""

    def get_compte_nom(self, obj) -> str:
        return str(obj.compte) if obj.compte_id else ""

    def get_acheteur_nom(self, obj) -> str:
        return str(obj.acheteur) if obj.acheteur_id else ""

    def get_situation_budget(self, obj):
        return obj.situation_budget()

    def get_motifs_dg(self, obj) -> list:
        return obj.motifs_dg()

    def get_signatures(self, obj) -> list:
        return [{"etape": libelle, "auteur": str(e.auteur) if e else "", "date": e.date if e else None}
                for libelle, e in obj.signatures()]

    def get_bons_commande(self, obj) -> list:
        return [{"id": b.id, "numero": b.numero, "statut_libelle": b.get_statut_display()} for b in obj.bons_commande.all()]

    def get_modifiable(self, obj) -> bool:
        return obj.modifiable and obj.demandeur_id == self._utilisateur().id

    def get_peut_valider(self, obj) -> bool:
        return obj.peut_valider(self._utilisateur())

    def get_peut_consulter(self, obj) -> bool:
        return obj.peut_consulter(self._utilisateur())

    def get_peut_imputer(self, obj) -> bool:
        return obj.peut_imputer(self._utilisateur())

    def get_peut_commander(self, obj) -> bool:
        return obj.statut == obj.Statut.VALIDEE and self._utilisateur().has_perm("achats.add_boncommande")

    def validate(self, attrs):
        demande, u = self.instance, self._utilisateur()
        if demande is None:
            autorises = CHAMPS_DEMANDEUR
        elif demande.modifiable and demande.demandeur_id == u.id:
            autorises = CHAMPS_DEMANDEUR - {"type"}  # le type fixe le numéro : il ne change plus
        elif demande.peut_consulter(u):
            autorises = CHAMPS_ACHATS
        elif demande.peut_imputer(u):
            autorises = CHAMPS_CONTROLE
        else:
            raise exceptions.PermissionDenied("Vous ne pouvez pas modifier cette demande à cette étape.")
        interdits = set(attrs) - autorises
        if interdits:
            raise serializers.ValidationError(f"À cette étape, vous ne pouvez pas modifier : {', '.join(sorted(interdits))}.")
        if sum(1 for d in attrs.get("devis", []) if d.get("retenu")) > 1:
            raise serializers.ValidationError("Un seul devis peut être retenu.")
        ligne = attrs.get("ligne_budgetaire")
        if ligne and not attrs.get("prevu_budget", demande.prevu_budget if demande else True):
            raise serializers.ValidationError("Un achat hors budget n'a pas de ligne budgétaire.")
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop("devis", None)
        return DemandeBudget.objects.create(**validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        devis = validated_data.pop("devis", None)
        if validated_data.get("prevu_budget") is False:
            validated_data["ligne_budgetaire"] = None
        instance = super().update(instance, validated_data)
        if devis is not None:
            instance.devis.all().delete()
            DevisDemande.objects.bulk_create(DevisDemande(demande=instance, **d) for d in devis)
            retenu = next((d for d in devis if d.get("retenu")), None)
            instance.montant = retenu["montant"] if retenu else None
            instance.save(update_fields=["montant"])
        return instance


class DemandeBudgetViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                           mixins.ListModelMixin, viewsets.GenericViewSet):
    """Demandes liées au budget. Pas de suppression : une demande reste dans l'historique."""

    serializer_class = DemandeBudgetSerializer
    queryset = DemandeBudget.objects.select_related(
        "demandeur", "service__responsable", "site", "projet", "client", "ligne_budgetaire__service", "acheteur",
        "service_impute", "compte",
    ).prefetch_related("devis__fournisseur", "evenements__auteur", "bons_commande")
    filterset_fields = ["type", "statut", "service", "site", "demandeur", "acheteur", "prevu_budget", "fast_track"]
    search_fields = ["numero", "ancien_numero", "intitule", "description", "devis__fournisseur__raison_sociale"]
    ordering_fields = ["cree_le", "date", "montant"]

    def get_queryset(self):
        qs = super().get_queryset()
        u = self.request.user
        if u.has_perm("achats.voir_toutes_demandebudget"):
            return qs
        # Chacun voit ses demandes ; un responsable voit aussi celles de son service.
        return qs.filter(Q(demandeur=u) | Q(service__responsable=u)).distinct()

    def perform_create(self, serializer):
        u = self.request.user
        serializer.save(demandeur=u, cree_par=u, modifie_par=u)

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
    def proposer(self, request, pk=None):
        return self._transition(request, "proposer")

    @action(**transition)
    def valider(self, request, pk=None):
        return self._transition(request, "valider", request.data.get("commentaire", ""))

    @action(**transition)
    def refuser(self, request, pk=None):
        return self._transition(request, "refuser", request.data.get("commentaire", ""))

    @action(**transition)
    def renvoyer(self, request, pk=None):
        return self._transition(request, "renvoyer", request.data.get("commentaire", ""))

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        demande = self.get_object()
        reponse = HttpResponse(pdf_demande_budget(demande), content_type="application/pdf")
        reponse["Content-Disposition"] = f'inline; filename="{demande.numero}.pdf"'
        return reponse
