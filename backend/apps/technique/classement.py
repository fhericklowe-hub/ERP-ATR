"""Coûts de réparation par équipement sur une période : pour repérer les équipements qui coûtent le plus cher à entretenir.

On compte les ordres de réparation ouverts pendant la période (hors annulés), avec la main-d'œuvre et les pièces chiffrées
comme sur chaque ordre. Réservé à qui peut voir les coûts."""
import datetime
from collections import defaultdict
from decimal import Decimal

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import exceptions, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.export import TYPE_XLSX, classeur_excel

from . import couts
from .models import Materiel, OrdreReparation


class CoutsPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.has_perm("technique.voir_couts_ordrereparation") and u.has_perm("technique.view_materiel"))


def _date(valeur, defaut):
    if not valeur:
        return defaut
    try:
        return datetime.date.fromisoformat(valeur)
    except ValueError:
        raise exceptions.ValidationError({"detail": "Date invalide."})


class CoutsParcViewSet(viewsets.ViewSet):
    permission_classes = [CoutsPermission]

    def _calculer(self, request):
        aujourdhui = timezone.localdate()
        debut = _date(request.query_params.get("debut"), aujourdhui.replace(month=1, day=1))
        fin = _date(request.query_params.get("fin"), aujourdhui)
        if fin < debut:
            raise exceptions.ValidationError({"detail": "La fin ne peut pas précéder le début."})
        filtres = {c: request.query_params[p] for p, c in (("site", "materiel__site_id"), ("type", "materiel__type"))
                   if request.query_params.get(p)}
        try:
            ordres = (OrdreReparation.objects.filter(cree_le__date__gte=debut, cree_le__date__lte=fin, **filtres)
                      .exclude(statut=OrdreReparation.Statut.ANNULE).select_related("materiel__site").prefetch_related("temps"))
            groupes = defaultdict(list)
            for o in ordres:
                groupes[o.materiel].append(o)
        except (ValueError, TypeError):
            raise exceptions.ValidationError({"detail": "Filtre invalide."})
        lignes = []
        for m, liste in groupes.items():
            total = {c: Decimal(0) for c in ("heures", "main_oeuvre", "pieces", "total")}
            for o in liste:
                c = couts.cout(o)
                for cle in total:
                    total[cle] += c[cle]
            lignes.append({"id": m.id, "code": m.code, "designation": m.designation, "type_libelle": m.get_type_display(),
                           "site_nom": m.site.nom, "annee": m.annee, "etat_libelle": m.get_etat_display(), "ordres": len(liste),
                           **total})
        lignes.sort(key=lambda l: l["total"], reverse=True)
        return {"debut": debut, "fin": fin, "lignes": lignes,
                "total": {c: sum((l[c] for l in lignes), Decimal(0)) for c in ("ordres", "heures", "main_oeuvre", "pieces", "total")}}

    def list(self, request):
        return Response(self._calculer(request))

    @action(detail=False, methods=["get"], url_path="exporter")
    def exporter(self, request):
        d = self._calculer(request)
        colonnes = [("N° de parc", "code", "texte"), ("Désignation", "designation", "texte"), ("Type", "type_libelle", "texte"),
                    ("Site", "site_nom", "texte"), ("Année", "annee", "texte"), ("État", "etat_libelle", "texte"),
                    ("Ordres", "ordres", "nombre"), ("Heures", "heures", "nombre"), ("Main-d'œuvre (XOF)", "main_oeuvre", "nombre"),
                    ("Pièces (XOF)", "pieces", "nombre"), ("Total (XOF)", "total", "nombre")]
        reponse = HttpResponse(classeur_excel("Coûts par équipement", colonnes, d["lignes"]), content_type=TYPE_XLSX)
        reponse["Content-Disposition"] = f'attachment; filename="couts-parc-{d["debut"]}-{d["fin"]}.xlsx"'
        return reponse
