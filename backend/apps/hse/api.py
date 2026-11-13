from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from rest_framework import exceptions, mixins, permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.achats.views import executer_transition

from .models import ActionCorrective, Evenement, Visite, indicateurs


class ActionSerializer(serializers.ModelSerializer):
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    responsable_nom = serializers.SerializerMethodField()
    evenement_numero = serializers.SerializerMethodField()
    visite_numero = serializers.SerializerMethodField()
    en_retard = serializers.BooleanField(read_only=True)
    peut_agir = serializers.SerializerMethodField()

    class Meta:
        model = ActionCorrective
        fields = ["id", "evenement", "evenement_numero", "visite", "visite_numero", "statut", "statut_libelle", "description",
                  "responsable", "responsable_nom", "echeance", "faite_le", "commentaire", "en_retard", "peut_agir"]

    def get_responsable_nom(self, obj) -> str:
        return str(obj.responsable)

    def get_evenement_numero(self, obj) -> str:
        return obj.evenement.numero if obj.evenement_id else ""

    def get_visite_numero(self, obj) -> str:
        return obj.visite.numero if obj.visite_id else ""

    def get_peut_agir(self, obj) -> bool:
        return obj.peut_agir(self.context["request"].user)

    def validate(self, attrs):
        u, a = self.context["request"].user, self.instance
        evenement = attrs.get("evenement", a.evenement if a else None)
        visite = attrs.get("visite", a.visite if a else None)
        if bool(evenement) == bool(visite):
            raise serializers.ValidationError("Une action vient d'un événement ou d'une visite de sécurité.")
        # Le visiteur décide des actions de sa propre visite ; tout le reste revient au responsable HSE.
        du_visiteur = not a and visite and visite.visiteur_id == u.id and u.has_perm("hse.add_visite")
        if not u.has_perm("hse.traiter_evenement") and not du_visiteur:
            raise exceptions.PermissionDenied("Les actions sont décidées par le responsable HSE, ou par le visiteur pour sa propre visite.")
        if a and ((evenement, visite) != (a.evenement, a.visite) or a.statut != ActionCorrective.Statut.A_FAIRE):
            raise serializers.ValidationError("Seule une action à faire se modifie, sans changer d'origine.")
        if evenement and evenement.statut == Evenement.Statut.CLOS:
            raise serializers.ValidationError("Cet événement est clos.")
        if visite and visite.statut == Visite.Statut.CLOSE:
            raise serializers.ValidationError("Cette visite est close.")
        return attrs


class EvenementSerializer(serializers.ModelSerializer):
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)
    gravite_libelle = serializers.CharField(source="get_gravite_display", read_only=True)
    site_nom = serializers.CharField(source="site.nom", read_only=True)
    materiel_nom = serializers.SerializerMethodField()
    declarant_nom = serializers.SerializerMethodField()
    clos_par_nom = serializers.SerializerMethodField()
    actions = ActionSerializer(many=True, read_only=True)
    actions_a_faire = serializers.SerializerMethodField()
    peut_traiter = serializers.SerializerMethodField()
    peut_modifier = serializers.SerializerMethodField()

    class Meta:
        model = Evenement
        fields = ["id", "numero", "statut", "statut_libelle", "type", "type_libelle", "gravite", "gravite_libelle", "date", "site", "site_nom",
                  "lieu", "description", "personnes", "materiel", "materiel_nom", "mesures_immediates", "jours_arret", "declarant_nom",
                  "causes", "conclusion", "clos_le", "clos_par_nom", "cree_le", "actions", "actions_a_faire", "peut_traiter", "peut_modifier"]

    def _u(self):
        return self.context["request"].user

    def get_materiel_nom(self, obj) -> str:
        return str(obj.materiel) if obj.materiel_id else ""

    def get_declarant_nom(self, obj) -> str:
        return str(obj.declarant)

    def get_clos_par_nom(self, obj) -> str:
        return str(obj.clos_par) if obj.clos_par_id else ""

    def get_actions_a_faire(self, obj) -> int:
        return sum(1 for a in obj.actions.all() if a.statut == ActionCorrective.Statut.A_FAIRE)

    def get_peut_traiter(self, obj) -> bool:
        return self._u().has_perm("hse.traiter_evenement")

    def get_peut_modifier(self, obj) -> bool:
        return _peut_modifier(obj, self._u())

    def validate(self, attrs):
        e = self.instance
        if e and not _peut_modifier(e, self._u()):
            raise exceptions.PermissionDenied("Une déclaration se corrige par son auteur tant qu'elle n'est pas analysée, ou par le responsable HSE.")
        champs = ("type", "date", "jours_arret")
        essai = Evenement(**{c: attrs.get(c, getattr(e, c) if e else Evenement._meta.get_field(c).get_default()) for c in champs})
        try:
            essai.clean()
        except DjangoValidationError as err:
            raise serializers.ValidationError(err.message_dict)
        return attrs


def _peut_modifier(evenement, u) -> bool:
    S = Evenement.Statut
    if u.has_perm("hse.traiter_evenement"):
        return evenement.statut != S.CLOS
    return evenement.statut == S.DECLARE and evenement.declarant_id == u.id


def _entier(valeur):
    if valeur in ("", None):
        return None
    try:
        nombre = int(valeur)
    except (TypeError, ValueError):
        raise exceptions.ValidationError({"detail": "Nombre de jours invalide."})
    if not 0 <= nombre <= 3650:
        raise exceptions.ValidationError({"detail": "Nombre de jours invalide."})
    return nombre


class EvenementViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, mixins.ListModelMixin,
                       viewsets.GenericViewSet):
    """Événements HSE. Chacun voit ses déclarations et celles où une action lui est confiée ; le responsable HSE voit tout."""

    serializer_class = EvenementSerializer
    queryset = Evenement.objects.all()
    filterset_fields = ["statut", "type", "gravite", "site", "materiel"]
    search_fields = ["numero", "description", "lieu", "personnes"]
    ordering_fields = ["date", "cree_le"]
    # Qui peut corriger quelle déclaration est décidé dans le sérialiseur (son auteur avant l'analyse, puis le responsable HSE).
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        u = self.request.user
        evenements = Evenement.objects.select_related("site", "materiel", "declarant", "clos_par").prefetch_related("actions__responsable")
        if u.has_perm("hse.traiter_evenement"):
            return evenements
        return evenements.filter(Q(declarant=u) | Q(actions__responsable=u)).distinct()

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        droit = "hse.add_evenement" if request.method == "POST" and self.action == "create" else "hse.view_evenement"
        if not request.user.has_perm(droit):
            raise exceptions.PermissionDenied()

    def perform_create(self, serializer):
        u = self.request.user
        serializer.save(declarant=u, cree_par=u, modifie_par=u)

    def perform_update(self, serializer):
        serializer.save(modifie_par=self.request.user)

    transition = dict(detail=True, methods=["post"])

    def _transition(self, request, nom, *args):
        executer_transition(self.get_object(), nom, request.user, *args)
        return Response(self.get_serializer(self.get_object()).data)

    @action(**transition)
    def analyser(self, request, pk=None):
        d = request.data
        return self._transition(request, "analyser", str(d.get("causes", "")), str(d.get("gravite") or "") or None, _entier(d.get("jours_arret")))

    @action(**transition)
    def clore(self, request, pk=None):
        return self._transition(request, "clore", str(request.data.get("conclusion", "")))

    @action(**transition)
    def rouvrir(self, request, pk=None):
        return self._transition(request, "rouvrir")

    @action(detail=False, methods=["get"])
    def indicateurs(self, request):
        """Chiffres de l'année, pour le responsable HSE."""
        if not request.user.has_perm("hse.traiter_evenement"):
            raise exceptions.PermissionDenied()
        return Response(indicateurs())


class ActionViewSet(mixins.CreateModelMixin, mixins.UpdateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """Actions correctives, nées d'un événement ou d'une visite de sécurité. `?miennes=1` : celles qui me sont confiées."""

    serializer_class = ActionSerializer
    queryset = ActionCorrective.objects.all()
    filterset_fields = ["statut", "evenement", "visite", "responsable"]
    ordering_fields = ["echeance"]

    def get_queryset(self):
        u = self.request.user
        actions = ActionCorrective.objects.select_related("evenement", "visite", "responsable")
        if self.request.query_params.get("miennes"):
            actions = actions.filter(responsable=u)
        elif not u.has_perm("hse.traiter_evenement"):
            actions = actions.filter(Q(responsable=u) | Q(visite__visiteur=u))
        return actions

    def perform_create(self, serializer):
        serializer.save(cree_par=self.request.user, modifie_par=self.request.user)

    def perform_update(self, serializer):
        serializer.save(modifie_par=self.request.user)

    transition = dict(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])

    def _transition(self, request, nom, *args):
        if not request.user.has_perm("hse.view_actioncorrective"):
            raise exceptions.PermissionDenied()
        executer_transition(self.get_object(), nom, request.user, *args)
        return Response(self.get_serializer(self.get_object()).data)

    @action(**transition)
    def terminer(self, request, pk=None):
        return self._transition(request, "terminer", str(request.data.get("commentaire", "")))

    @action(**transition)
    def abandonner(self, request, pk=None):
        return self._transition(request, "abandonner", str(request.data.get("commentaire", "")))
