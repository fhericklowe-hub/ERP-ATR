"""Import des fournisseurs ou des clients depuis un classeur Excel.

Première feuille ; les titres des colonnes sont sur la première ligne utile (quelques lignes de titre au-dessus sont
tolérées), dans n'importe quel ordre. Obligatoire : raison sociale.
Facultatives : code, n° contribuable, téléphone, e-mail, adresse, ville. Un tiers déjà connu (même code, ou à défaut
même raison sociale) est mis à jour, les autres sont créés. L'import ajoute la qualité choisie (fournisseur ou
client) sans retirer l'autre : un même tiers peut être les deux."""
import re
from itertools import islice

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import validate_email
from django.db import transaction
from openpyxl import load_workbook

from apps.core.models import Compteur
from apps.stock.imports import _cle

from .models import Tiers

COLONNES = {
    "code": ("code", "code tiers", "code fournisseur", "code client", "n compte", "compte", "numero", "n"),
    "raison_sociale": ("raison sociale", "nom", "societe", "fournisseur", "client", "denomination", "libelle"),
    "numero_contribuable": ("n contribuable", "numero contribuable", "compte contribuable", "ncc", "n cc", "contribuable"),
    "telephone": ("telephone", "tel", "contact"),
    "email": ("e-mail", "email", "mail", "courriel"),
    "adresse": ("adresse", "boite postale", "bp"),
    "ville": ("ville", "localite"),
    "statut": ("statut",),
}
IGNORER_STATUTS = {"hors perimetre"}  # lignes d'un annuaire marquées « hors périmètre » : ni créées ni modifiées
LIGNES_TITRES = 10
TEXTES = {"numero_contribuable": 50, "telephone": 100, "adresse": 500, "ville": 100}
QUALITES = {"fournisseur": "est_fournisseur", "client": "est_client"}
LIGNES_MAX = 5000


def _texte(valeur) -> str:
    """Une case en texte : un code saisi comme nombre (516890.0) redevient « 516890 »."""
    if isinstance(valeur, float) and valeur == int(valeur):
        valeur = int(valeur)
    return str(valeur if valeur is not None else "").strip()


def _titre(cellule) -> str:
    """Un titre de colonne comparable : sans accent, sans « n° » collé, sans le commentaire entre parenthèses."""
    return _cle(re.sub(r"\([^)]*\)", " ", str(cellule or "").replace("°", " ")))


def importer(utilisateur, fichier, qualite, simuler=False) -> dict:
    """Lit le classeur et crée ou met à jour les tiers. Avec `simuler`, rien n'est écrit : on obtient le compte
    rendu. S'il y a une seule ligne en erreur, rien n'est écrit non plus."""
    if not (utilisateur.has_perm("referentiels.add_tiers") and utilisateur.has_perm("referentiels.change_tiers")):
        raise PermissionDenied("Vous n'avez pas le droit de créer et de modifier les tiers.")
    if qualite not in QUALITES:
        raise ValidationError("Précisez s'il s'agit de fournisseurs ou de clients.")
    drapeau = QUALITES[qualite]
    try:
        feuille = load_workbook(fichier, data_only=True, read_only=True).worksheets[0]
    except Exception:
        raise ValidationError("Fichier illisible : il faut un classeur Excel (.xlsx).")
    toutes = list(feuille.iter_rows(values_only=True))
    if not toutes:
        raise ValidationError("Le classeur est vide.")
    # La ligne des titres est la première, parmi les premières lignes, qui contient une colonne « raison sociale ».
    entete = next((i for i, l in enumerate(islice(toutes, LIGNES_TITRES))
                   if any(_titre(c) in COLONNES["raison_sociale"] for c in l)), None)
    if entete is None:
        raise ValidationError("Colonne manquante. Colonnes attendues : raison sociale, puis au besoin code, n° contribuable, "
                              "téléphone, e-mail, adresse, ville.")
    titres = [_titre(c) for c in toutes[entete]]
    col = {nom: next((titres.index(t) for t in variantes if t in titres), None) for nom, variantes in COLONNES.items()}
    lignes = toutes[entete + 1:]
    # Une colonne « N° » qui numérote simplement les lignes (1, 2, 3…) n'est pas un code de tiers.
    if col["code"] is not None:
        valeurs = [_texte(l[col["code"]]) if col["code"] < len(l) else "" for l in lignes]
        if any(valeurs) and all(v == "" or (v.isdigit() and int(v) == i + 1) for i, v in enumerate(valeurs)):
            col["code"] = None

    bilan = {"lues": 0, "crees": 0, "modifies": 0, "inchanges": 0, "ignorees": 0, "avertissements": [], "erreurs": [], "simulation": simuler}
    vus = set()
    with transaction.atomic():
        for n, ligne in enumerate(lignes, start=entete + 2):
            def lire(nom):
                return _texte(ligne[col[nom]]) if col[nom] is not None and col[nom] < len(ligne) else ""

            code, raison = lire("code"), lire("raison_sociale")
            if not (code or raison):
                continue
            if _cle(lire("statut")) in IGNORER_STATUTS:
                bilan["ignorees"] += 1
                continue
            bilan["lues"] += 1
            if bilan["lues"] > LIGNES_MAX:
                raise ValidationError(f"Trop de lignes : {LIGNES_MAX} au plus par fichier.")
            try:
                if not raison:
                    raise ValueError("raison sociale manquante")
                if len(code) > 20 or len(raison) > 200:
                    raise ValueError("code (20 caractères au plus) ou raison sociale (200) trop long")
                cle = ("c", code.lower()) if code else ("r", _cle(raison))
                if cle in vus:
                    raise ValueError(f"{code or raison} figure deux fois")
                vus.add(cle)
                if code:
                    connus = list(Tiers.objects.filter(code__iexact=code))
                else:
                    connus = list(Tiers.objects.filter(raison_sociale__iexact=raison))
                    if len(connus) > 1:
                        raise ValueError("plusieurs tiers portent ce nom : indiquez le code")
                tiers = connus[0] if connus else None
                nouveau = tiers is None
                tiers = tiers or Tiers(code=code, cree_par=utilisateur)
                valeurs = {"raison_sociale": raison, drapeau: True}
                for champ, longueur in TEXTES.items():
                    if lire(champ):
                        valeurs[champ] = lire(champ)[:longueur]
                if lire("email"):
                    # Plusieurs adresses dans la même case : on garde la première, et on le signale.
                    adresses = [a for a in re.split(r"[;,/\s]+", lire("email")) if a]
                    if len(adresses) > 1:
                        bilan["avertissements"].append(f"Ligne {n} : plusieurs e-mails, le premier est gardé ({adresses[0]}).")
                    try:
                        validate_email(adresses[0])
                    except ValidationError:
                        raise ValueError(f"e-mail invalide (« {lire('email')} »)")
                    valeurs["email"] = adresses[0]
                if not (nouveau or any(getattr(tiers, c) != v for c, v in valeurs.items())):
                    bilan["inchanges"] += 1
                    continue
                for c, v in valeurs.items():
                    setattr(tiers, c, v)
                if not tiers.code:   # pas de code dans le fichier : numéro automatique
                    tiers.code = f"T{Compteur.suivant('TIERS'):05d}"
                    while Tiers.objects.filter(code=tiers.code).exists():
                        tiers.code = f"T{Compteur.suivant('TIERS'):05d}"
                tiers.modifie_par = utilisateur
                tiers.save()
                bilan["crees" if nouveau else "modifies"] += 1
            except ValueError as e:
                bilan["erreurs"].append(f"Ligne {n} : {e}.")
        if simuler or bilan["erreurs"]:
            transaction.set_rollback(True)
    bilan["erreurs"] = bilan["erreurs"][:50]
    bilan["avertissements"] = bilan["avertissements"][:50]
    bilan["ecrit"] = not simuler and not bilan["erreurs"]
    return bilan
