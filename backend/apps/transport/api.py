import datetime
from collections import defaultdict
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import exceptions, mixins, permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.achats.views import executer_transition
from apps.core.api import VueMetier
from apps.core.export import ExportExcel

from .models import OrdreTransport

KM = serializers.IntegerField(min_value=0, allow_null=True)
LITRES = serializers.DecimalField(max_digits=8, decimal_places=1, min_value=0, allow_null=True)


def _moment(valeur):
    if not valeur:
        return None
    try:
        moment = datetime.datetime.fromisoformat(str(valeur).replace("Z", "+00:00"))
    except ValueError:
        raise exceptions.ValidationError({"detail": "Date invalide."})
    return moment if timezone.is_aware(moment) else timezone.make_aware(moment)


def _nombre(champ, valeur):
    return champ.run_validation(valeur if valeur not in ("", None) else None)


class OrdreTransportSerializer(serializers.ModelSerializer):
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    client_nom = serializers.CharField(source="client.raison_sociale", read_only=True)
    site_nom = serializers.CharField(source="site.nom", read_only=True)
    tracteur_nom = serializers.CharField(source="tracteur.__str__", read_only=True)
    tracteur_compteur_km = serializers.IntegerField(source="tracteur.compteur_km", read_only=True)
    remorque_nom = serializers.SerializerMethodField()
    km_parcourus = serializers.IntegerField(read_only=True)
    consommation_100km = serializers.DecimalField(max_digits=6, decimal_places=1, read_only=True)
    peut_agir = serializers.SerializerMethodField()

    class Meta:
        model = OrdreTransport
        fields = ["id", "numero", "statut", "statut_libelle", "client", "client_nom", "reference_client", "site", "site_nom",
                  "origine", "destination", "marchandise", "poids_tonnes", "nombre_colis", "date_prevue", "tracteur", "tracteur_nom",
                  "tracteur_compteur_km", "remorque", "remorque_nom", "chauffeur", "prix_ht", "observations", "depart_le",
                  "km_depart", "arrivee_le", "km_arrivee", "carburant_litres", "km_parcourus", "consommation_100km", "reserves",
                  "motif_annulation", "peut_agir"]
        read_only_fields = ["depart_le", "km_depart", "arrivee_le", "km_arrivee", "carburant_litres", "reserves", "motif_annulation"]
        extra_kwargs = {"prix_ht": {"min_value": 0}, "poids_tonnes": {"min_value": 0}}

    def get_remorque_nom(self, obj) -> str:
        return str(obj.remorque) if obj.remorque_id else ""

    def get_peut_agir(self, obj) -> bool:
        return self.context["request"].user.has_perm("transport.change_ordretransport")

    def validate_client(self, client):
        if not client.est_client or not client.actif:
            raise serializers.ValidationError("Ce tiers n'est pas un client actif.")
        return client

    def validate(self, attrs):
        o = self.instance
        if o and o.statut != OrdreTransport.Statut.PLANIFIE:
            raise serializers.ValidationError("Un ordre parti ou terminé ne se modifie plus.")
        essai = OrdreTransport(**{c: attrs.get(c, getattr(o, c, None)) for c in ("tracteur", "remorque")})
        try:
            essai.clean()
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.message_dict)
        return attrs


class OrdreTransportViewSet(ExportExcel, mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                            mixins.ListModelMixin, viewsets.GenericViewSet):
    """Ordres de transport. Pas de suppression : un ordre abandonné s'annule, avec son motif."""

    export_titre, export_fichier = "Ordres de transport", "ordres-transport"
    export_colonnes = [
        ("N°", "numero"), ("État", "statut_libelle"), ("Client", "client_nom"), ("Référence client", "reference_client"),
        ("Agence", "site_nom"), ("Chargement", "origine"), ("Livraison", "destination"), ("Marchandise", "marchandise"),
        ("Poids (t)", "poids_tonnes", "nombre"), ("Départ prévu", "date_prevue", "date"), ("Tracteur", "tracteur_nom"),
        ("Remorque", "remorque_nom"), ("Chauffeur", "chauffeur"), ("Parti le", "depart_le", "date"), ("Livré le", "arrivee_le", "date"),
        ("Km parcourus", "km_parcourus", "nombre"), ("Carburant (l)", "carburant_litres", "nombre"),
        ("Conso (l/100 km)", "consommation_100km", "nombre"), ("Prix HT", "prix_ht", "nombre"),
    ]
    serializer_class = OrdreTransportSerializer
    queryset = OrdreTransport.objects.select_related("client", "site", "tracteur", "remorque")
    filterset_fields = ["statut", "client", "site", "tracteur", "date_prevue"]
    search_fields = ["numero", "client__raison_sociale", "reference_client", "origine", "destination", "chauffeur", "tracteur__code"]
    ordering_fields = ["date_prevue", "cree_le"]

    perform_create = VueMetier.perform_create
    perform_update = VueMetier.perform_update

    transition = dict(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])

    def _transition(self, request, nom, *args):
        if not request.user.has_perm("transport.view_ordretransport"):
            raise exceptions.PermissionDenied()
        executer_transition(self.get_object(), nom, request.user, *args)
        return Response(self.get_serializer(self.get_object()).data)

    @action(**transition)
    def demarrer(self, request, pk=None):
        d = request.data
        return self._transition(request, "demarrer", _moment(d.get("moment")), _nombre(KM, d.get("km")))

    @action(**transition)
    def livrer(self, request, pk=None):
        d = request.data
        return self._transition(request, "livrer", _moment(d.get("moment")), _nombre(KM, d.get("km")),
                                _nombre(LITRES, d.get("litres")), str(d.get("reserves", "")))

    @action(**transition)
    def annuler(self, request, pk=None):
        return self._transition(request, "annuler", str(request.data.get("motif", "")))

    @action(detail=False, methods=["get"])
    def synthese(self, request):
        """Par tracteur et par chauffeur, sur les ordres livrés entre `debut` et `fin` : trajets, kilomètres, carburant, consommation."""
        aujourdhui = timezone.localdate()
        try:
            debut = datetime.date.fromisoformat(request.query_params.get("debut") or aujourdhui.replace(day=1).isoformat())
            fin = datetime.date.fromisoformat(request.query_params.get("fin") or aujourdhui.isoformat())
        except ValueError:
            raise exceptions.ValidationError({"detail": "Date invalide."})
        ordres = self.filter_queryset(self.get_queryset()).filter(
            statut=OrdreTransport.Statut.LIVRE, arrivee_le__date__gte=debut, arrivee_le__date__lte=fin)

        def regrouper(cle):
            groupes = defaultdict(list)
            for o in ordres:
                groupes[cle(o)].append(o)
            lignes = []
            for nom, liste in groupes.items():
                km = sum(o.km_parcourus or 0 for o in liste)
                avec_carburant = [o for o in liste if o.carburant_litres is not None and o.km_parcourus]
                litres = sum((o.carburant_litres for o in avec_carburant), Decimal(0))
                km_mesures = sum(o.km_parcourus for o in avec_carburant)
                lignes.append({"nom": nom, "ordres": len(liste), "km": km, "litres": litres,
                               "consommation_100km": (litres * 100 / km_mesures).quantize(Decimal("0.1")) if km_mesures else None})
            return sorted(lignes, key=lambda l: -l["km"])

        return Response({"debut": debut, "fin": fin, "ordres": ordres.count(),
                         "par_tracteur": regrouper(lambda o: str(o.tracteur)), "par_chauffeur": regrouper(lambda o: o.chauffeur)})
