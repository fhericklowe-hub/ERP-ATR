"""Import du parc de matériels depuis un classeur Excel.

Première feuille, première ligne = titres des colonnes, dans n'importe quel ordre. Obligatoires : n° de parc,
désignation, type, site. Facultatives : marque, modèle, n° de série, immatriculation, année, capacité, activité,
compteur heures, compteur km, mise en service. Un n° de parc déjà connu est mis à jour, les autres sont créés."""
import datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from openpyxl import load_workbook

from apps.achats.choix import Activite
from apps.core.models import Site
from apps.stock.imports import _cle, _nombre

from .models import Materiel

COLONNES = {
    "code": ("n de parc", "no de parc", "numero de parc", "n parc", "code", "parc"),
    "designation": ("designation", "libelle", "materiel", "engin"),
    "type": ("type", "categorie", "famille"),
    "site": ("site", "site de rattachement", "agence"),
    "marque": ("marque",),
    "modele": ("modele",),
    "numero_serie": ("n de serie", "no de serie", "numero de serie", "serie", "chassis", "n de chassis"),
    "immatriculation": ("immatriculation", "immat", "plaque"),
    "annee": ("annee",),
    "capacite": ("capacite", "tonnage"),
    "activite": ("activite",),
    "compteur_heures": ("compteur heures", "heures", "compteur h", "compteur (heures)"),
    "compteur_km": ("compteur km", "km", "kilometrage", "compteur (km)"),
    "date_mise_en_service": ("mise en service", "date de mise en service"),
}
TEXTES = {"designation": 150, "marque": 60, "modele": 60, "numero_serie": 60, "immatriculation": 30, "capacite": 40}
# Mots usuels acceptés en plus des libellés exacts des types.
SYNONYMES = {"chariot": "CHARIOT", "chariot elevateur": "CHARIOT", "grue": "GRUE", "grue mobile": "GRUE", "nacelle": "NACELLE",
             "camion": "CAMION", "porteur": "CAMION", "tracteur": "TRACTEUR", "tracteur routier": "TRACTEUR",
             "remorque": "REMORQUE", "semi-remorque": "REMORQUE", "semi remorque": "REMORQUE", "porte-char": "REMORQUE",
             "vehicule": "VEHICULE", "vehicule leger": "VEHICULE", "voiture": "VEHICULE", "pick-up": "VEHICULE",
             "groupe": "GROUPE", "groupe electrogene": "GROUPE", "compresseur": "GROUPE", "autre": "AUTRE"}
LIGNES_MAX = 2000


def _date(valeur):
    if valeur in (None, ""):
        return None
    if isinstance(valeur, datetime.datetime):
        return valeur.date()
    if isinstance(valeur, datetime.date):
        return valeur
    for forme in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(str(valeur).strip(), forme).date()
        except ValueError:
            pass
    raise ValueError(f"date de mise en service illisible (« {valeur} »)")


def importer(utilisateur, fichier, simuler=False) -> dict:
    """Lit le classeur et crée ou met à jour les matériels. Avec `simuler`, rien n'est écrit : on obtient le compte
    rendu. S'il y a une seule ligne en erreur, rien n'est écrit non plus."""
    if not (utilisateur.has_perm("technique.add_materiel") and utilisateur.has_perm("technique.change_materiel")):
        raise PermissionDenied("Seul le chef d'atelier peut importer le parc.")
    try:
        feuille = load_workbook(fichier, data_only=True, read_only=True).worksheets[0]
    except Exception:
        raise ValidationError("Fichier illisible : il faut un classeur Excel (.xlsx).")
    lignes = feuille.iter_rows(values_only=True)
    try:
        titres = [_cle(str(c or "").replace("°", " ")) for c in next(lignes)]
    except StopIteration:
        raise ValidationError("Le classeur est vide.")
    col = {nom: next((titres.index(t) for t in variantes if t in titres), None) for nom, variantes in COLONNES.items()}
    if col["code"] is None or col["designation"] is None:
        raise ValidationError("Colonne manquante. Colonnes attendues : n° de parc, désignation, type, site, puis au besoin "
                              "marque, modèle, n° de série, immatriculation, année, capacité, activité, compteur heures, "
                              "compteur km, mise en service.")

    types = {**SYNONYMES, **{_cle(v): v for v, _ in Materiel.Type.choices}, **{_cle(l): v for v, l in Materiel.Type.choices}}
    activites = {**{_cle(v): v for v, _ in Activite.choices}, **{_cle(l): v for v, l in Activite.choices}}
    sites = {}
    for s in Site.objects.all():
        sites[_cle(s.code)] = sites[_cle(s.nom)] = s
    bilan = {"lues": 0, "crees": 0, "modifies": 0, "inchanges": 0, "erreurs": [], "simulation": simuler}
    vus = set()
    with transaction.atomic():
        for n, ligne in enumerate(lignes, start=2):
            def lire(nom):
                v = ligne[col[nom]] if col[nom] is not None and col[nom] < len(ligne) else None
                return v.strip() if isinstance(v, str) else v

            code = str(lire("code") or "").strip()
            if not code and not lire("designation"):
                continue
            bilan["lues"] += 1
            if bilan["lues"] > LIGNES_MAX:
                raise ValidationError(f"Trop de lignes : {LIGNES_MAX} au plus par fichier.")
            try:
                if not code:
                    raise ValueError("n° de parc manquant")
                if len(code) > 30:
                    raise ValueError("n° de parc trop long (30 caractères au plus)")
                if code.lower() in vus:
                    raise ValueError(f"le n° de parc {code} figure deux fois")
                vus.add(code.lower())
                materiel = Materiel.objects.filter(code__iexact=code).first()
                nouveau = materiel is None
                materiel = materiel or Materiel(code=code, cree_par=utilisateur)
                valeurs = {}
                for champ, longueur in TEXTES.items():
                    if lire(champ) not in (None, ""):
                        valeurs[champ] = str(lire(champ))[:longueur]
                if lire("type") not in (None, ""):
                    if _cle(lire("type")) not in types:
                        raise ValueError(f"type inconnu (« {lire('type')} »)")
                    valeurs["type"] = types[_cle(lire("type"))]
                if lire("site") not in (None, ""):
                    if _cle(lire("site")) not in sites:
                        raise ValueError(f"site inconnu (« {lire('site')} »)")
                    valeurs["site"] = sites[_cle(lire("site"))]
                if lire("activite") not in (None, ""):
                    if _cle(lire("activite")) not in activites:
                        raise ValueError(f"activité inconnue (« {lire('activite')} »)")
                    valeurs["activite"] = activites[_cle(lire("activite"))]
                annee = _nombre(lire("annee"), "année")
                if annee is not None:
                    if not 1950 <= annee <= 2100 or annee != int(annee):
                        raise ValueError(f"année invraisemblable (« {lire('annee')} »)")
                    valeurs["annee"] = int(annee)
                heures, km = _nombre(lire("compteur_heures"), "compteur heures"), _nombre(lire("compteur_km"), "compteur km")
                if heures is not None:
                    valeurs["compteur_heures"] = heures.quantize(type(heures)("0.1"))
                if km is not None:
                    valeurs["compteur_km"] = int(km)
                mise = _date(lire("date_mise_en_service"))
                if mise:
                    valeurs["date_mise_en_service"] = mise
                if nouveau:
                    manque = [nom for nom in ("designation", "type", "site") if nom not in valeurs]
                    if manque:
                        raise ValueError(", ".join(manque).replace("designation", "désignation") + " manquant pour un matériel nouveau")
                change = nouveau or any(getattr(materiel, c) != v for c, v in valeurs.items())
                if not change:
                    bilan["inchanges"] += 1
                    continue
                for c, v in valeurs.items():
                    setattr(materiel, c, v)
                materiel.modifie_par = utilisateur
                materiel.save()
                bilan["crees" if nouveau else "modifies"] += 1
            except ValueError as e:
                bilan["erreurs"].append(f"Ligne {n} : {e}.")
        if simuler or bilan["erreurs"]:
            transaction.set_rollback(True)
    bilan["erreurs"] = bilan["erreurs"][:50]
    bilan["ecrit"] = not simuler and not bilan["erreurs"]
    return bilan
