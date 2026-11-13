import datetime
from io import BytesIO

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import exceptions, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .valorisation import consommations, valeur_du_stock


def _jour(valeur, defaut):
    if not valeur:
        return defaut
    try:
        return datetime.date.fromisoformat(valeur)
    except ValueError:
        raise exceptions.ValidationError({"detail": "Date invalide."})


def _magasin(valeur):
    try:
        return int(valeur) if valeur else None
    except ValueError:
        raise exceptions.ValidationError({"detail": "Magasin inconnu."})


class VueValeur(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not request.user.has_perm("stock.voir_valeur_stock"):
            raise exceptions.PermissionDenied("La valeur du stock est réservée au responsable du stock et au contrôle de gestion.")


class ValeurStock(VueValeur):
    """Stock valorisé au coût moyen pondéré. `?date=` (valeur à cette date), `?magasin=`, `?search=`,
    `?export=xlsx` pour le fichier Excel."""

    def get(self, request):
        p = request.query_params
        aujourd_hui = timezone.localdate()
        jour = _jour(p.get("date"), aujourd_hui)
        if jour > aujourd_hui:
            raise exceptions.ValidationError({"detail": "La date ne peut pas être dans le futur."})
        etat = valeur_du_stock(jour, _magasin(p.get("magasin")), (p.get("search") or "").strip())
        if p.get("export") == "xlsx":
            return _excel(etat, jour)
        return Response({"date": jour, "count": len(etat["lignes"]), "total": etat["total"], "sans_prix": etat["sans_prix"],
                         "results": etat["lignes"][:1000]})


class Consommations(VueValeur):
    """Valeur des sorties de stock sur une période, par service et par OR. `?debut=`, `?fin=`, `?magasin=`."""

    def get(self, request):
        p = request.query_params
        aujourd_hui = timezone.localdate()
        debut, fin = _jour(p.get("debut"), aujourd_hui.replace(day=1)), _jour(p.get("fin"), aujourd_hui)
        if fin < debut:
            raise exceptions.ValidationError({"detail": "La période est invalide."})
        return Response({"debut": debut, "fin": fin, **consommations(debut, fin, _magasin(p.get("magasin")))})


def _excel(etat, jour):
    from openpyxl import Workbook
    from openpyxl.styles import Font

    classeur = Workbook()
    feuille = classeur.active
    feuille.title = "Stock valorisé"
    feuille.append([f"Stock valorisé au {jour:%d/%m/%Y} (coût moyen pondéré, XOF)"])
    feuille.append([])
    feuille.append(["Code", "Désignation", "Nature", "Magasin", "Unité", "Quantité", "Coût moyen", "Valeur"])
    for l in etat["lignes"]:
        feuille.append([l["code"], l["designation"], l["nature"], l["magasin_nom"], l["unite"], float(l["quantite"]),
                        None if l["cout_moyen"] is None else float(l["cout_moyen"]), None if l["valeur"] is None else int(l["valeur"])])
    feuille.append([])
    feuille.append(["", "", "", "", "", "", "Total", int(etat["total"])])
    for cellule in (*feuille[1], *feuille[3], *feuille[feuille.max_row]):
        cellule.font = Font(bold=True)
    for colonne, largeur in zip("ABCDEFGH", (16, 44, 18, 22, 8, 12, 14, 16)):
        feuille.column_dimensions[colonne].width = largeur
    tampon = BytesIO()
    classeur.save(tampon)
    reponse = HttpResponse(tampon.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    reponse["Content-Disposition"] = f'attachment; filename="stock-valorise-{jour:%Y-%m-%d}.xlsx"'
    return reponse
