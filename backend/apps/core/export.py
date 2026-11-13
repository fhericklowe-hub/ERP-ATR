"""Export Excel d'une liste : le même contenu et les mêmes filtres que l'écran, mais sans la pagination.

Un ViewSet qui hérite de `ExportExcel` gagne l'adresse `…/exporter/`, qui accepte les filtres, la recherche et le tri de
la liste. Les colonnes se déclarent avec `export_colonnes` : (titre, chemin dans la sortie du sérialiseur, type), où le
chemin peut descendre dans un dictionnaire (`totaux.total_ttc`) et le type vaut `texte` (défaut), `nombre`, `date` ou
`oui_non`. Chacun n'exporte que ce que la liste lui montre : les droits et la visibilité sont ceux du ViewSet."""

from datetime import date, datetime
from decimal import Decimal
from io import BytesIO

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import exceptions
from rest_framework.decorators import action

LIMITE_LIGNES = 5000
TYPE_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _valeur(ligne, chemin):
    for morceau in chemin.split("."):
        if not isinstance(ligne, dict):
            return None
        ligne = ligne.get(morceau)
    return None if isinstance(ligne, (list, dict)) else ligne


def _convertir(valeur, type_):
    if valeur is None or valeur == "":
        return None
    if type_ == "nombre":
        return float(Decimal(str(valeur)))
    if type_ == "oui_non":
        return "Oui" if valeur else "Non"
    if type_ == "date":
        if isinstance(valeur, datetime):
            return timezone.localtime(valeur).date() if timezone.is_aware(valeur) else valeur.date()
        if isinstance(valeur, date):
            return valeur
        texte = str(valeur)
        if len(texte) > 10:
            return timezone.localtime(datetime.fromisoformat(texte)).date()
        return date.fromisoformat(texte)
    return valeur if isinstance(valeur, (int, float)) else str(valeur)


def classeur_excel(titre_feuille, colonnes, lignes):
    """Un classeur : titres en gras sur la première ligne (figée, avec filtre), largeurs ajustées au contenu."""
    from openpyxl import Workbook
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter

    classeur = Workbook()
    feuille = classeur.active
    feuille.title = titre_feuille[:31]
    feuille.append([titre for titre, _chemin, _type in colonnes])
    for cellule in feuille[1]:
        cellule.font = Font(bold=True)
    largeurs = [len(titre) for titre, _chemin, _type in colonnes]
    for ligne in lignes:
        valeurs = [_convertir(_valeur(ligne, chemin), type_) for _titre, chemin, type_ in colonnes]
        feuille.append(valeurs)
        for i, v in enumerate(valeurs):
            largeurs[i] = max(largeurs[i], len(v.strftime("%d/%m/%Y") if isinstance(v, date) else f"{v:,.0f}" if isinstance(v, float) else str(v or "")))
    for i, (_titre, _chemin, type_) in enumerate(colonnes, start=1):
        feuille.column_dimensions[get_column_letter(i)].width = min(max(largeurs[i - 1] + 2, 8), 50)
        if type_ in ("date", "nombre"):
            decimales = type_ == "nombre" and any(
                isinstance(c.value, float) and c.value != int(c.value) for c in feuille[get_column_letter(i)][1:])
            for cellule in feuille[get_column_letter(i)][1:]:
                cellule.number_format = "dd/mm/yyyy" if type_ == "date" else "#,##0.00" if decimales else "#,##0"
    feuille.freeze_panes = "A2"
    feuille.auto_filter.ref = feuille.dimensions
    tampon = BytesIO()
    classeur.save(tampon)
    return tampon.getvalue()


class ExportExcel:
    export_titre = "Export"
    export_fichier = "export"
    export_colonnes: list[tuple[str, str, str]] = []

    @action(detail=False, methods=["get"], url_path="exporter")
    def exporter(self, request):
        lignes = self.filter_queryset(self.get_queryset())
        total = lignes.count()
        if total > LIMITE_LIGNES:
            raise exceptions.ValidationError(
                {"detail": f"{total} lignes : trop pour un seul fichier (au plus {LIMITE_LIGNES}). Précisez les filtres."})
        donnees = self.get_serializer(lignes, many=True).data
        colonnes = [c if len(c) == 3 else (*c, "texte") for c in self.export_colonnes]
        reponse = HttpResponse(classeur_excel(self.export_titre, colonnes, donnees), content_type=TYPE_XLSX)
        reponse["Content-Disposition"] = f'attachment; filename="{self.export_fichier}-{timezone.localdate():%Y-%m-%d}.xlsx"'
        return reponse
