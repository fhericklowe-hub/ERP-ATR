import datetime

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from rest_framework import exceptions, mixins, permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.achats.views import executer_transition

from .conges import DemandeAbsence, jours_ouvrables, solde_conges
from .models import Salarie


def voit_tout(u) -> bool:
    return u.has_perm("rh.approuver_demandeabsence") or u.has_perm("rh.view_salarie")


def visibles(u):
    """Les RH voient tout ; les autres, leurs demandes et celles des salariés dont ils sont le responsable."""
    demandes = DemandeAbsence.objects.select_related("salarie__responsable__utilisateur", "salarie__service__responsable",
                                                     "salarie__site", "vise_par", "approuve_par")
    if voit_tout(u):
        return demandes
    return demandes.filter(Q(salarie__utilisateur=u) | Q(salarie__responsable__utilisateur=u) | Q(salarie__service__responsable=u))


def _salarie_de(u):
    return Salarie.objects.filter(utilisateur=u).first()


class DemandeAbsenceSerializer(serializers.ModelSerializer):
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)
    salarie = serializers.PrimaryKeyRelatedField(queryset=Salarie.objects.all(), required=False)
    salarie_nom = serializers.CharField(source="salarie.__str__", read_only=True)
    matricule = serializers.CharField(source="salarie.matricule", read_only=True)
    site_nom = serializers.CharField(source="salarie.site.nom", read_only=True)
    vise_par_nom = serializers.SerializerMethodField()
    approuve_par_nom = serializers.SerializerMethodField()
    peut_viser = serializers.SerializerMethodField()
    peut_approuver = serializers.SerializerMethodField()
    peut_annuler = serializers.SerializerMethodField()

    class Meta:
        model = DemandeAbsence
        fields = ["id", "numero", "statut", "statut_libelle", "salarie", "salarie_nom", "matricule", "site_nom", "type", "type_libelle",
                  "date_debut", "date_fin", "jours", "motif", "vise_par_nom", "vise_le", "approuve_par_nom", "approuve_le", "commentaire",
                  "cree_le", "peut_viser", "peut_approuver", "peut_annuler"]

    def _u(self):
        return self.context["request"].user

    def get_vise_par_nom(self, obj) -> str:
        return str(obj.vise_par) if obj.vise_par_id else ""

    def get_approuve_par_nom(self, obj) -> str:
        return str(obj.approuve_par) if obj.approuve_par_id else ""

    def get_peut_viser(self, obj) -> bool:
        return obj.peut_viser(self._u())

    def get_peut_approuver(self, obj) -> bool:
        return obj.peut_approuver(self._u())

    def get_peut_annuler(self, obj) -> bool:
        return obj.peut_annuler(self._u())

    def validate(self, attrs):
        u = self._u()
        le_sien = _salarie_de(u)
        salarie = attrs.get("salarie") or le_sien
        if not salarie:
            raise serializers.ValidationError("Votre compte n'est relié à aucun dossier de salarié : voyez les RH.")
        if salarie != le_sien and not u.has_perm("rh.approuver_demandeabsence"):
            raise exceptions.PermissionDenied("Vous ne pouvez demander une absence que pour vous-même.")
        attrs["salarie"] = salarie
        try:
            DemandeAbsence(**attrs).clean()
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.message_dict if hasattr(e, "error_dict") else {"detail": e.messages})
        return attrs


def _jour(valeur, defaut=None):
    if not valeur:
        return defaut
    try:
        return datetime.date.fromisoformat(str(valeur))
    except ValueError:
        raise exceptions.ValidationError({"detail": "Date invalide."})


class DemandeAbsenceViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """Demandes de congé et d'absence. Une demande ne se modifie pas : on l'annule et on en refait une."""

    serializer_class = DemandeAbsenceSerializer
    queryset = DemandeAbsence.objects.all()
    filterset_fields = ["statut", "type", "salarie", "salarie__site", "salarie__service"]
    search_fields = ["numero", "salarie__nom", "salarie__prenoms", "salarie__matricule"]
    ordering_fields = ["date_debut", "cree_le"]

    def get_queryset(self):
        demandes = visibles(self.request.user)
        p, u = self.request.query_params, self.request.user
        if p.get("vue") == "miennes":
            demandes = demandes.filter(salarie__utilisateur=u)
        elif p.get("vue") == "a_traiter":
            S = DemandeAbsence.Statut
            a_viser = Q(statut=S.SOUMISE) & (Q(salarie__responsable__utilisateur=u) | Q(salarie__service__responsable=u))
            demandes = demandes.filter(a_viser | Q(statut=S.VISEE) if u.has_perm("rh.approuver_demandeabsence") else a_viser)
            demandes = demandes.exclude(salarie__utilisateur=u)
        return demandes

    def perform_create(self, serializer):
        serializer.save(cree_par=self.request.user, modifie_par=self.request.user)

    transition = dict(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])

    def _transition(self, request, nom, *args):
        if not request.user.has_perm("rh.view_demandeabsence"):
            raise exceptions.PermissionDenied()
        executer_transition(self.get_object(), nom, request.user, *args)
        return Response(self.get_serializer(self.get_object()).data)

    @action(**transition)
    def viser(self, request, pk=None):
        return self._transition(request, "viser")

    @action(**transition)
    def approuver(self, request, pk=None):
        return self._transition(request, "approuver")

    @action(**transition)
    def refuser(self, request, pk=None):
        return self._transition(request, "refuser", str(request.data.get("commentaire", "")))

    @action(**transition)
    def annuler(self, request, pk=None):
        return self._transition(request, "annuler", str(request.data.get("commentaire", "")))

    @action(detail=False, methods=["get"])
    def solde(self, request):
        """Solde de congés : le sien, ou celui de `?salarie=` pour les RH et son responsable."""
        u, p = request.user, request.query_params
        salarie = _salarie_de(u)
        if p.get("salarie"):
            try:
                salarie = Salarie.objects.select_related("responsable__utilisateur", "service__responsable").get(pk=int(p["salarie"]))
            except (Salarie.DoesNotExist, ValueError):
                raise exceptions.ValidationError({"detail": "Salarié inconnu."})
            from .conges import responsable_de
            if not (voit_tout(u) or salarie.utilisateur_id == u.id or responsable_de(salarie) == u):
                raise exceptions.PermissionDenied()
        if not salarie:
            return Response({"salarie": None})
        return Response({"salarie": salarie.id, "salarie_nom": str(salarie), **solde_conges(salarie)})

    @action(detail=False, methods=["get"])
    def calcul(self, request):
        """Nombre de jours ouvrables entre `?debut=` et `?fin=`."""
        debut, fin = _jour(request.query_params.get("debut")), _jour(request.query_params.get("fin"))
        return Response({"jours": jours_ouvrables(debut, fin) if debut and fin else 0})

    @action(detail=False, methods=["get"])
    def planning(self, request):
        """Absences approuvées ou en attente qui touchent la période `?debut=`…`?fin=` (30 jours par défaut)."""
        debut = _jour(request.query_params.get("debut"), datetime.date.today())
        fin = _jour(request.query_params.get("fin"), debut + datetime.timedelta(days=30))
        S = DemandeAbsence.Statut
        demandes = visibles(request.user).filter(date_debut__lte=fin, date_fin__gte=debut, statut__in=[S.SOUMISE, S.VISEE, S.APPROUVEE])
        return Response(self.get_serializer(demandes.order_by("date_debut", "salarie__nom"), many=True).data)
