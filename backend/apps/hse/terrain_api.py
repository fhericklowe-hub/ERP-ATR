from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.utils import timezone
from rest_framework import exceptions, mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.achats.views import executer_transition
from apps.core.api import VueMetier
from apps.rh.models import Salarie

from .api import ActionSerializer
from .models import ActionCorrective
from .terrain import DotationEPI, Visite, renouvellements


def _verifier(modele, champs, attrs, instance):
    """Applique les règles du modèle (clean) aux valeurs reçues, complétées par celles déjà enregistrées."""
    essai = modele(**{c: attrs.get(c, getattr(instance, c) if instance else modele._meta.get_field(c).get_default()) for c in champs})
    try:
        essai.clean()
    except DjangoValidationError as err:
        raise serializers.ValidationError(err.message_dict)


def _peut_modifier(visite, u) -> bool:
    return visite.statut == Visite.Statut.OUVERTE and (visite.visiteur_id == u.id or u.has_perm("hse.traiter_evenement"))


class VisiteSerializer(serializers.ModelSerializer):
    statut_libelle = serializers.SerializerMethodField()
    site_nom = serializers.CharField(source="site.nom", read_only=True)
    visiteur_nom = serializers.SerializerMethodField()
    actions = ActionSerializer(many=True, read_only=True)
    actions_a_faire = serializers.SerializerMethodField()
    peut_modifier = serializers.SerializerMethodField()
    peut_clore = serializers.SerializerMethodField()

    class Meta:
        model = Visite
        fields = ["id", "numero", "statut", "statut_libelle", "date", "site", "site_nom", "lieu", "participants", "visiteur_nom",
                  "points_positifs", "ecarts", "clos_le", "actions", "actions_a_faire", "peut_modifier", "peut_clore"]

    def get_statut_libelle(self, obj) -> str:
        if obj.statut == Visite.Statut.OUVERTE and not self.get_actions_a_faire(obj):
            return "À clore"
        return obj.get_statut_display()

    def get_visiteur_nom(self, obj) -> str:
        return str(obj.visiteur)

    def get_actions_a_faire(self, obj) -> int:
        return sum(1 for a in obj.actions.all() if a.statut == ActionCorrective.Statut.A_FAIRE)

    def get_peut_modifier(self, obj) -> bool:
        return _peut_modifier(obj, self.context["request"].user)

    def get_peut_clore(self, obj) -> bool:
        return self.context["request"].user.has_perm("hse.traiter_evenement")

    def validate(self, attrs):
        if self.instance and not _peut_modifier(self.instance, self.context["request"].user):
            raise exceptions.PermissionDenied("Une visite se corrige par son visiteur ou le responsable HSE, tant qu'elle n'est pas close.")
        _verifier(Visite, ("date", "points_positifs", "ecarts"), attrs, self.instance)
        return attrs


class VisiteViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, mixins.ListModelMixin,
                    viewsets.GenericViewSet):
    """Visites de sécurité. Chacun voit celles qu'il a menées et celles où une action lui est confiée ; le responsable HSE voit tout."""

    serializer_class = VisiteSerializer
    queryset = Visite.objects.all()
    filterset_fields = ["statut", "site", "visiteur"]
    search_fields = ["numero", "lieu", "participants", "ecarts", "points_positifs"]
    ordering_fields = ["date"]

    def get_queryset(self):
        u = self.request.user
        visites = Visite.objects.select_related("site", "visiteur").prefetch_related("actions__responsable", "actions__visite", "actions__evenement")
        if u.has_perm("hse.traiter_evenement"):
            return visites
        return visites.filter(Q(visiteur=u) | Q(actions__responsable=u)).distinct()

    def perform_create(self, serializer):
        u = self.request.user
        serializer.save(visiteur=u, cree_par=u, modifie_par=u)

    def perform_update(self, serializer):
        serializer.save(modifie_par=self.request.user)

    transition = dict(detail=True, methods=["post"])

    def _transition(self, request, nom):
        executer_transition(self.get_object(), nom, request.user)
        return Response(self.get_serializer(self.get_object()).data)

    @action(**transition)
    def clore(self, request, pk=None):
        return self._transition(request, "clore")

    @action(**transition)
    def rouvrir(self, request, pk=None):
        return self._transition(request, "rouvrir")


class DotationSerializer(serializers.ModelSerializer):
    equipement_libelle = serializers.CharField(source="get_equipement_display", read_only=True)
    salarie_nom = serializers.SerializerMethodField()
    matricule = serializers.CharField(source="salarie.matricule", read_only=True)
    site_nom = serializers.CharField(source="salarie.site.nom", read_only=True)
    remis_par_nom = serializers.SerializerMethodField()
    jours = serializers.SerializerMethodField()

    class Meta:
        model = DotationEPI
        fields = ["id", "salarie", "salarie_nom", "matricule", "site_nom", "equipement", "equipement_libelle", "precision", "quantite",
                  "date_remise", "a_renouveler_le", "jours", "remis_par_nom", "observations"]

    def get_salarie_nom(self, obj) -> str:
        return str(obj.salarie)

    def get_remis_par_nom(self, obj) -> str:
        return str(obj.remis_par)

    def get_jours(self, obj):
        """Jours restants avant le renouvellement (négatif : dépassé)."""
        return (obj.a_renouveler_le - timezone.localdate()).days if obj.a_renouveler_le else None

    def validate(self, attrs):
        if self.instance and "salarie" in attrs and attrs["salarie"] != self.instance.salarie:
            raise serializers.ValidationError({"salarie": "Une dotation ne change pas de salarié : supprimez-la et saisissez-la à nouveau."})
        if not self.instance and attrs["salarie"].statut != Salarie.Statut.ACTIF:
            raise serializers.ValidationError({"salarie": "Ce salarié n'est plus en poste."})
        _verifier(DotationEPI, ("date_remise", "a_renouveler_le", "quantite"), attrs, self.instance)
        return attrs


class DotationViewSet(VueMetier):
    """Équipements de protection remis aux salariés. `?salarie=` : la fiche d'un salarié."""

    serializer_class = DotationSerializer
    queryset = DotationEPI.objects.select_related("salarie__site", "remis_par")
    filterset_fields = ["salarie", "equipement", "salarie__site"]
    search_fields = ["salarie__nom", "salarie__prenoms", "salarie__matricule", "precision"]
    ordering_fields = ["date_remise", "a_renouveler_le"]

    def perform_create(self, serializer):
        u = self.request.user
        serializer.save(remis_par=u, cree_par=u, modifie_par=u)

    @action(detail=False, methods=["get"])
    def salaries(self, request):
        """Salariés en poste, réduits à ce qu'il faut pour leur remettre un équipement : le dossier RH reste fermé."""
        return Response([{"id": s.id, "nom": str(s), "matricule": s.matricule, "site_nom": s.site.nom}
                         for s in Salarie.objects.filter(statut=Salarie.Statut.ACTIF).select_related("site").order_by("nom", "prenoms")])

    @action(detail=False, methods=["get"])
    def renouvellements(self, request):
        """Équipements à renouveler dans les 30 jours (ou `?jours=`), ou dont la date est dépassée."""
        try:
            jours = min(max(int(request.query_params.get("jours", 30)), 0), 365)
        except ValueError:
            raise exceptions.ValidationError({"detail": "Nombre de jours invalide."})
        return Response(self.get_serializer(renouvellements(jours), many=True).data)
