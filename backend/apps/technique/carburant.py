"""Pleins de carburant du parc : qui a pris combien, quand, à quel compteur. Avec les compteurs on obtient la
consommation de chaque équipement (litres aux 100 km pour les routiers, litres à l'heure pour les engins)."""
import datetime
from collections import defaultdict
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone
from rest_framework import exceptions, mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.api import VueMetier
from apps.core.export import ExportExcel
from apps.core.models import Horodate


class PleinCarburant(Horodate):
    materiel = models.ForeignKey("technique.Materiel", on_delete=models.PROTECT, related_name="pleins", verbose_name="matériel")
    date = models.DateField(default=timezone.localdate)
    litres = models.DecimalField(max_digits=8, decimal_places=1, validators=[MinValueValidator(Decimal("0.1"))])
    montant = models.DecimalField("montant payé (XOF)", max_digits=12, decimal_places=2, null=True, blank=True,
                                  validators=[MinValueValidator(0)])
    compteur_heures = models.DecimalField("compteur (heures)", max_digits=10, decimal_places=1, null=True, blank=True)
    compteur_km = models.PositiveIntegerField("compteur (km)", null=True, blank=True)
    lieu = models.CharField("station ou cuve", max_length=120, blank=True)
    conducteur = models.CharField("conducteur ou opérateur", max_length=120, blank=True)
    reference = models.CharField("n° de ticket ou de bon", max_length=60, blank=True)

    class Meta:
        verbose_name = "plein de carburant"
        verbose_name_plural = "pleins de carburant"
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.materiel.code} · {self.litres} l le {self.date:%d/%m/%Y}"


class PleinSerializer(serializers.ModelSerializer):
    materiel_nom = serializers.CharField(source="materiel.__str__", read_only=True)
    site_nom = serializers.CharField(source="materiel.site.nom", read_only=True)
    saisi_par = serializers.SerializerMethodField()

    class Meta:
        model = PleinCarburant
        fields = ["id", "materiel", "materiel_nom", "site_nom", "date", "litres", "montant", "compteur_heures", "compteur_km",
                  "lieu", "conducteur", "reference", "saisi_par"]
        extra_kwargs = {"compteur_heures": {"min_value": 0}}

    def get_saisi_par(self, obj) -> str:
        return str(obj.cree_par) if obj.cree_par_id else ""

    def validate(self, attrs):
        if attrs.get("date", timezone.localdate()) > timezone.localdate():
            raise serializers.ValidationError({"date": "La date ne peut pas être dans le futur."})
        if self.instance is None and attrs["materiel"].etat == attrs["materiel"].Etat.REFORME:
            raise serializers.ValidationError({"materiel": "Ce matériel est réformé."})
        if self.instance is not None and attrs.get("materiel", self.instance.materiel) != self.instance.materiel:
            raise serializers.ValidationError({"materiel": "Le matériel d'un plein ne se change pas."})
        return attrs


def _synthese(pleins) -> list:
    """Par matériel : litres, montant, et consommation calculée entre le premier et le dernier compteur relevés.
    Le premier plein sert de point de départ : ses litres ne comptent pas dans la consommation."""
    groupes = defaultdict(list)
    for p in pleins:
        groupes[p.materiel].append(p)
    lignes = []
    for m, liste in groupes.items():
        liste.sort(key=lambda p: (p.date, p.id))
        ligne = {"id": m.id, "code": m.code, "designation": m.designation, "site_nom": m.site.nom, "pleins": len(liste),
                 "litres": sum((p.litres for p in liste), Decimal(0)),
                 "montant": sum((p.montant for p in liste if p.montant is not None), Decimal(0)),
                 "km": None, "consommation_100km": None, "heures": None, "consommation_heure": None}
        for champ, cle, taux, facteur in (("compteur_km", "km", "consommation_100km", 100), ("compteur_heures", "heures", "consommation_heure", 1)):
            releves = [p for p in liste if getattr(p, champ) is not None]
            if len(releves) >= 2:
                ecart = getattr(releves[-1], champ) - getattr(releves[0], champ)
                if ecart > 0:
                    apres = [p for p in liste if (p.date, p.id) > (releves[0].date, releves[0].id) and (p.date, p.id) <= (releves[-1].date, releves[-1].id)]
                    litres = sum((p.litres for p in apres), Decimal(0))
                    ligne[cle] = ecart
                    ligne[taux] = (litres * facteur / Decimal(ecart)).quantize(Decimal("0.1"))
        lignes.append(ligne)
    return sorted(lignes, key=lambda l: -l["litres"])


class PleinViewSet(ExportExcel, mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                   mixins.ListModelMixin, viewsets.GenericViewSet):
    """Pleins de carburant. Pas de suppression : une erreur de saisie se corrige."""

    export_titre, export_fichier = "Pleins de carburant", "pleins-carburant"
    export_colonnes = [("Date", "date", "date"), ("Matériel", "materiel_nom"), ("Site", "site_nom"), ("Litres", "litres", "nombre"),
                       ("Montant (XOF)", "montant", "nombre"), ("Compteur heures", "compteur_heures", "nombre"),
                       ("Compteur km", "compteur_km", "nombre"), ("Station ou cuve", "lieu"), ("Conducteur", "conducteur"),
                       ("Ticket", "reference"), ("Saisi par", "saisi_par")]
    serializer_class = PleinSerializer
    queryset = PleinCarburant.objects.select_related("materiel__site", "cree_par")
    filterset_fields = {"materiel": ["exact"], "materiel__site": ["exact"], "date": ["gte", "lte"]}
    search_fields = ["materiel__code", "materiel__designation", "conducteur", "lieu", "reference"]
    ordering_fields = ["date"]

    @transaction.atomic
    def perform_create(self, serializer):
        VueMetier.perform_create(self, serializer)
        self._relever(serializer.instance)

    @transaction.atomic
    def perform_update(self, serializer):
        VueMetier.perform_update(self, serializer)
        self._relever(serializer.instance)

    def _relever(self, plein):
        """Le compteur relevé au plein met la fiche du matériel à jour, s'il avance."""
        m, champs = plein.materiel, []
        if plein.compteur_heures is not None and (m.compteur_heures is None or plein.compteur_heures > m.compteur_heures):
            m.compteur_heures = plein.compteur_heures
            champs.append("compteur_heures")
        if plein.compteur_km is not None and (m.compteur_km is None or plein.compteur_km > m.compteur_km):
            m.compteur_km = plein.compteur_km
            champs.append("compteur_km")
        if champs:
            m.save(update_fields=champs + ["modifie_le"])

    @action(detail=False, methods=["get"])
    def synthese(self, request):
        """Par matériel entre `debut` et `fin` : litres, montant et consommation d'après les compteurs."""
        aujourdhui = timezone.localdate()
        try:
            debut = datetime.date.fromisoformat(request.query_params.get("debut") or aujourdhui.replace(month=1, day=1).isoformat())
            fin = datetime.date.fromisoformat(request.query_params.get("fin") or aujourdhui.isoformat())
        except ValueError:
            raise exceptions.ValidationError({"detail": "Date invalide."})
        pleins = self.get_queryset().filter(date__gte=debut, date__lte=fin)
        if request.query_params.get("site"):
            try:
                pleins = pleins.filter(materiel__site_id=int(request.query_params["site"]))
            except ValueError:
                raise exceptions.ValidationError({"detail": "Site invalide."})
        lignes = _synthese(pleins)
        return Response({"debut": debut, "fin": fin, "lignes": lignes,
                         "total": {"pleins": sum(l["pleins"] for l in lignes), "litres": sum((l["litres"] for l in lignes), Decimal(0)),
                                   "montant": sum((l["montant"] for l in lignes), Decimal(0))}})
