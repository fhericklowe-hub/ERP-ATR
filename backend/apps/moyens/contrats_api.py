from django.db.models import Q
from django.utils import timezone
from rest_framework import mixins, permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.achats.views import executer_transition
from apps.core.api import VueMetier

from .contrats import Contrat, Echeance


class ContratSerializer(serializers.ModelSerializer):
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)
    periodicite_libelle = serializers.CharField(source="get_periodicite_display", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    prestataire_nom = serializers.CharField(source="prestataire.raison_sociale", read_only=True)
    site_nom = serializers.CharField(source="site.nom", read_only=True, default="")
    bien_nom = serializers.SerializerMethodField()
    date_limite_preavis = serializers.DateField(read_only=True)

    class Meta:
        model = Contrat
        fields = [
            "id", "numero", "type", "type_libelle", "objet", "prestataire", "prestataire_nom", "reference", "site",
            "site_nom", "bien", "bien_nom", "date_debut", "date_fin", "tacite_reconduction", "preavis_jours",
            "date_limite_preavis", "montant", "periodicite", "periodicite_libelle", "statut", "statut_libelle",
            "observations",
        ]

    def get_bien_nom(self, obj) -> str:
        return str(obj.bien) if obj.bien_id else ""

    def validate(self, attrs):
        debut = attrs.get("date_debut", getattr(self.instance, "date_debut", None))
        fin = attrs.get("date_fin", getattr(self.instance, "date_fin", None))
        if debut and fin and fin < debut:
            raise serializers.ValidationError({"date_fin": "La date de fin est avant la date de début."})
        return attrs


class SansSuppression(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                      mixins.ListModelMixin, viewsets.GenericViewSet):
    perform_create = VueMetier.perform_create
    perform_update = VueMetier.perform_update


class ContratViewSet(SansSuppression):
    """Contrats des moyens généraux. Pas de suppression : un contrat terminé passe à « résilié ou terminé »."""

    serializer_class = ContratSerializer
    queryset = Contrat.objects.select_related("prestataire", "site", "bien")
    filterset_fields = ["type", "statut", "site", "prestataire", "bien"]
    search_fields = ["numero", "objet", "reference", "prestataire__raison_sociale"]
    ordering_fields = ["date_debut", "date_fin", "montant"]


class EcheanceSerializer(serializers.ModelSerializer):
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    situation = serializers.CharField(read_only=True)
    jours_restants = serializers.SerializerMethodField()
    site_nom = serializers.CharField(source="site.nom", read_only=True, default="")
    bien_nom = serializers.SerializerMethodField()
    contrat_numero = serializers.CharField(source="contrat.numero", read_only=True, default="")

    class Meta:
        model = Echeance
        fields = [
            "id", "type", "type_libelle", "libelle", "date_echeance", "rappel_jours", "recurrence_mois", "site",
            "site_nom", "bien", "bien_nom", "contrat", "contrat_numero", "montant_prevu", "statut", "statut_libelle",
            "situation", "jours_restants", "faite_le", "montant_reel", "commentaire",
        ]
        read_only_fields = ["statut", "faite_le", "montant_reel"]

    def get_bien_nom(self, obj) -> str:
        return str(obj.bien) if obj.bien_id else ""

    def get_jours_restants(self, obj) -> int:
        return (obj.date_echeance - timezone.localdate()).days

    def validate(self, attrs):
        if self.instance and self.instance.statut != Echeance.Statut.A_FAIRE:
            raise serializers.ValidationError("Cette échéance n'est plus à faire et ne peut plus être modifiée.")
        return attrs


class EcheanceViewSet(SansSuppression):
    """Échéances à ne pas manquer. `?situation=RETARD`, `PROCHE` ou `ALERTE` (les deux) filtre celles à traiter."""

    serializer_class = EcheanceSerializer
    queryset = Echeance.objects.select_related("site", "bien", "contrat")
    filterset_fields = {"type": ["exact"], "statut": ["exact"], "site": ["exact"], "bien": ["exact"],
                        "contrat": ["exact"], "date_echeance": ["lte", "gte"]}
    search_fields = ["libelle", "bien__designation", "bien__numero", "bien__immatriculation", "contrat__numero"]
    ordering_fields = ["date_echeance"]

    def get_queryset(self):
        qs = super().get_queryset()
        situation = self.request.query_params.get("situation")
        if self.action != "list" or not situation:
            return qs
        jour = timezone.localdate()
        a_faire = qs.filter(statut=Echeance.Statut.A_FAIRE)
        retard = Q(date_echeance__lt=jour)
        # date_echeance - rappel_jours <= aujourd'hui, comparé jour par jour pour rester portable entre bases.
        proche_ids = [
            id for id, echeance, rappel in a_faire.filter(date_echeance__gte=jour)
            .values_list("id", "date_echeance", "rappel_jours") if (echeance - jour).days <= rappel
        ]
        proche = Q(id__in=proche_ids)
        if situation == "RETARD":
            return a_faire.filter(retard)
        if situation == "PROCHE":
            return a_faire.filter(proche)
        if situation == "ALERTE":
            return a_faire.filter(retard | proche)
        return qs

    transition = dict(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])

    @action(**transition)
    def faire(self, request, pk=None):
        d = request.data
        date_ = serializers.DateField(allow_null=True)
        montant = serializers.DecimalField(max_digits=14, decimal_places=0, min_value=0, allow_null=True).run_validation(
            d.get("montant") if d.get("montant") not in ("", None) else None)
        suivante = executer_transition(
            self.get_object(), "faire", request.user, date_.run_validation(d.get("faite_le") or None), montant,
            d.get("commentaire", ""), date_.run_validation(d.get("prochaine") or None))
        donnees = self.get_serializer(self.get_object()).data
        donnees["suivante"] = self.get_serializer(suivante).data if suivante else None
        return Response(donnees)

    @action(**transition)
    def annuler(self, request, pk=None):
        executer_transition(self.get_object(), "annuler", request.user, request.data.get("commentaire", ""))
        return Response(self.get_serializer(self.get_object()).data)
