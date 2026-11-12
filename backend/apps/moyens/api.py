from django.db.models import Q
from rest_framework import exceptions, mixins, permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.achats.views import executer_transition
from apps.core.api import VueMetier
from apps.core.models import Utilisateur
from apps.referentiels.models import Tiers

from .models import Bien, DemandeIntervention, Evenement


class BienSerializer(serializers.ModelSerializer):
    categorie_libelle = serializers.CharField(source="get_categorie_display", read_only=True)
    etat_libelle = serializers.CharField(source="get_etat_display", read_only=True)
    site_nom = serializers.CharField(source="site.nom", read_only=True)
    service_nom = serializers.CharField(source="service.nom", read_only=True, default="")
    affecte_a_nom = serializers.SerializerMethodField()
    interventions_ouvertes = serializers.SerializerMethodField()

    class Meta:
        model = Bien
        fields = [
            "id", "numero", "categorie", "categorie_libelle", "designation", "marque", "modele", "numero_serie",
            "immatriculation", "site", "site_nom", "emplacement", "service", "service_nom", "affecte_a", "affecte_a_nom",
            "date_acquisition", "valeur_acquisition", "fournisseur", "etat", "etat_libelle", "observations",
            "interventions_ouvertes",
        ]

    def get_affecte_a_nom(self, obj) -> str:
        return str(obj.affecte_a) if obj.affecte_a_id else ""

    def get_interventions_ouvertes(self, obj) -> int:
        S = DemandeIntervention.Statut
        return sum(1 for i in obj.interventions.all() if i.statut in (S.NOUVELLE, S.PRISE_EN_CHARGE, S.REALISEE))


class BienViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                  mixins.ListModelMixin, viewsets.GenericViewSet):
    """Inventaire des biens. Pas de suppression : un bien sorti de l'inventaire passe à l'état réformé."""

    serializer_class = BienSerializer
    queryset = Bien.objects.select_related("site", "service", "affecte_a").prefetch_related("interventions")
    filterset_fields = ["categorie", "etat", "site", "service", "affecte_a"]
    search_fields = ["numero", "designation", "marque", "modele", "numero_serie", "immatriculation", "emplacement"]
    ordering_fields = ["numero", "designation", "date_acquisition"]

    perform_create = VueMetier.perform_create
    perform_update = VueMetier.perform_update


class EvenementSerializer(serializers.ModelSerializer):
    auteur_nom = serializers.CharField(source="auteur.__str__", read_only=True)
    action_libelle = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = Evenement
        fields = ["id", "action", "action_libelle", "statut", "auteur_nom", "date", "commentaire"]


class DemandeInterventionSerializer(serializers.ModelSerializer):
    evenements = EvenementSerializer(many=True, read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    categorie_libelle = serializers.CharField(source="get_categorie_display", read_only=True)
    priorite_libelle = serializers.CharField(source="get_priorite_display", read_only=True)
    demandeur_nom = serializers.CharField(source="demandeur.__str__", read_only=True)
    service_nom = serializers.CharField(source="service.nom", read_only=True)
    site_nom = serializers.CharField(source="site.nom", read_only=True)
    bien_nom = serializers.SerializerMethodField()
    intervenant_nom = serializers.SerializerMethodField()
    prestataire_nom = serializers.CharField(source="prestataire.raison_sociale", read_only=True, default="")
    modifiable = serializers.SerializerMethodField()
    peut_traiter = serializers.SerializerMethodField()
    peut_realiser = serializers.SerializerMethodField()
    peut_cloturer = serializers.SerializerMethodField()

    class Meta:
        model = DemandeIntervention
        fields = [
            "id", "numero", "statut", "statut_libelle", "cree_le", "demandeur", "demandeur_nom", "service", "service_nom",
            "site", "site_nom", "lieu", "bien", "bien_nom", "categorie", "categorie_libelle", "priorite",
            "priorite_libelle", "objet", "description", "intervenant", "intervenant_nom", "prestataire",
            "prestataire_nom", "date_prevue", "prise_en_charge_le", "realisee_le", "compte_rendu", "cout", "cloturee_le",
            "modifiable", "peut_traiter", "peut_realiser", "peut_cloturer", "evenements",
        ]
        # La prise en charge et la réalisation passent par les actions du circuit, pas par une modification directe.
        read_only_fields = ["numero", "statut", "demandeur", "intervenant", "prestataire", "date_prevue",
                            "prise_en_charge_le", "realisee_le", "compte_rendu", "cout", "cloturee_le"]

    def _u(self):
        return self.context["request"].user

    def get_bien_nom(self, obj) -> str:
        return str(obj.bien) if obj.bien_id else ""

    def get_intervenant_nom(self, obj) -> str:
        return str(obj.intervenant) if obj.intervenant_id else ""

    def get_modifiable(self, obj) -> bool:
        return obj.modifiable and obj.demandeur_id == self._u().id

    def get_peut_traiter(self, obj) -> bool:
        return obj.peut_traiter(self._u())

    def get_peut_realiser(self, obj) -> bool:
        return obj.statut == obj.Statut.PRISE_EN_CHARGE and (obj.peut_traiter(self._u()) or obj.intervenant_id == self._u().id)

    def get_peut_cloturer(self, obj) -> bool:
        return obj.demandeur_id == self._u().id or obj.peut_traiter(self._u())

    def validate(self, attrs):
        if self.instance and not self.instance.modifiable:
            raise serializers.ValidationError("Cette demande est déjà prise en charge et ne peut plus être modifiée.")
        return attrs


class DemandeInterventionViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                                 mixins.ListModelMixin, viewsets.GenericViewSet):
    """Demandes d'intervention. Pas de suppression : une demande reste dans l'historique."""

    serializer_class = DemandeInterventionSerializer
    queryset = DemandeIntervention.objects.select_related(
        "demandeur", "service", "site", "bien", "intervenant", "prestataire"
    ).prefetch_related("evenements__auteur")
    filterset_fields = ["statut", "categorie", "priorite", "site", "service", "demandeur", "intervenant", "prestataire", "bien"]
    search_fields = ["numero", "objet", "description", "lieu", "bien__designation", "bien__numero"]
    ordering_fields = ["cree_le", "priorite", "date_prevue"]

    def get_queryset(self):
        qs = super().get_queryset()
        u = self.request.user
        if u.has_perm("moyens.voir_toutes_demandeintervention"):
            return qs
        # Chacun voit ses demandes, celles qu'il doit réaliser, et un responsable celles de son service.
        return qs.filter(Q(demandeur=u) | Q(intervenant=u) | Q(service__responsable=u)).distinct()

    def perform_create(self, serializer):
        u = self.request.user
        demande = serializer.save(demandeur=u, cree_par=u, modifie_par=u)
        # Signaler une panne sur un bien le fait passer « en panne » dans l'inventaire.
        if demande.bien_id and demande.bien.etat == Bien.Etat.EN_SERVICE and self.request.data.get("bien_en_panne"):
            Bien.objects.filter(pk=demande.bien_id).update(etat=Bien.Etat.EN_PANNE)

    def update(self, request, *args, **kwargs):
        if self.get_object().demandeur_id != request.user.id:
            raise exceptions.PermissionDenied("Seul le demandeur peut modifier sa demande.")
        return super().update(request, *args, **kwargs)

    def perform_update(self, serializer):
        serializer.save(modifie_par=self.request.user)

    transition = dict(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])

    def _transition(self, request, nom, *args):
        executer_transition(self.get_object(), nom, request.user, *args)
        return Response(self.get_serializer(self.get_object()).data)

    @action(**transition)
    def prendre_en_charge(self, request, pk=None):
        d = request.data
        try:
            intervenant = Utilisateur.objects.get(pk=d["intervenant"], is_active=True) if d.get("intervenant") else None
            prestataire = Tiers.objects.get(pk=d["prestataire"], est_fournisseur=True) if d.get("prestataire") else None
        except (Utilisateur.DoesNotExist, Tiers.DoesNotExist, ValueError):
            raise exceptions.ValidationError({"detail": "Intervenant ou prestataire inconnu."})
        date_prevue = serializers.DateField(allow_null=True).run_validation(d.get("date_prevue") or None)
        return self._transition(request, "prendre_en_charge", intervenant, prestataire, date_prevue, d.get("commentaire", ""))

    @action(**transition)
    def realiser(self, request, pk=None):
        d = request.data
        cout = serializers.DecimalField(max_digits=14, decimal_places=0, min_value=0, allow_null=True).run_validation(
            d.get("cout") if d.get("cout") not in ("", None) else None)
        realisee_le = serializers.DateField(allow_null=True).run_validation(d.get("realisee_le") or None)
        return self._transition(request, "realiser", d.get("compte_rendu", ""), cout, realisee_le)

    @action(**transition)
    def cloturer(self, request, pk=None):
        return self._transition(request, "cloturer", request.data.get("commentaire", ""))

    @action(**transition)
    def rouvrir(self, request, pk=None):
        return self._transition(request, "rouvrir", request.data.get("commentaire", ""))

    @action(**transition)
    def refuser(self, request, pk=None):
        return self._transition(request, "refuser", request.data.get("commentaire", ""))
