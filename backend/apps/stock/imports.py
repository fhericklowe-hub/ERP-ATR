"""Import du stock de départ (ou d'un inventaire complet) depuis un classeur Excel.

Première feuille, première ligne = titres des colonnes. Colonnes reconnues, dans n'importe quel ordre :
code, désignation, unité, quantité (obligatoires sauf unité), seuil, rangement, prix.
Les articles inconnus sont créés. Le stock du magasin est mis à la quantité du fichier."""
import unicodedata
from decimal import Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from openpyxl import load_workbook

from apps.referentiels.models import Article, Unite

from .models import Mouvement, ReglageStock, exiger_magasin, quantite_en_stock, verrouiller

COLONNES = {
    "code": ("code", "code article", "reference", "ref"),
    "designation": ("designation", "libelle", "article"),
    "unite": ("unite", "u"),
    "quantite": ("quantite", "qte", "stock", "quantite en stock"),
    "seuil": ("seuil", "seuil mini", "seuil d'alerte", "stock mini"),
    "casier": ("rangement", "casier", "emplacement"),
    "prix": ("prix", "prix unitaire", "pu"),
}
LIGNES_MAX = 5000


def _cle(texte) -> str:
    sans_accent = unicodedata.normalize("NFKD", str(texte or "")).encode("ascii", "ignore").decode()
    return " ".join(sans_accent.lower().replace(".", " ").split())


def _nombre(valeur, nom):
    if valeur in (None, ""):
        return None
    try:
        n = Decimal(str(valeur).replace(" ", "").replace(" ", "").replace(",", ".")).quantize(Decimal("0.01"))
    except InvalidOperation:
        raise ValueError(f"{nom} illisible (« {valeur} »)")
    if n < 0:
        raise ValueError(f"{nom} négatif")
    return n


def importer(utilisateur, fichier, magasin, simuler=False) -> dict:
    """Lit le classeur et met le stock du magasin à jour. Avec `simuler`, rien n'est écrit : on obtient le compte rendu.
    S'il y a une seule ligne en erreur, rien n'est écrit non plus."""
    if not utilisateur.has_perm("stock.ajuster_stock"):
        raise PermissionDenied("Seul le responsable du stock peut importer un stock.")
    exiger_magasin(magasin)
    try:
        feuille = load_workbook(fichier, data_only=True, read_only=True).worksheets[0]
    except Exception:
        raise ValidationError("Fichier illisible : il faut un classeur Excel (.xlsx).")
    lignes = feuille.iter_rows(values_only=True)
    try:
        titres = [_cle(c) for c in next(lignes)]
    except StopIteration:
        raise ValidationError("Le classeur est vide.")
    col = {nom: next((titres.index(t) for t in variantes if t in titres), None) for nom, variantes in COLONNES.items()}
    manquantes = [n for n in ("code", "designation", "quantite") if col[n] is None]
    if manquantes:
        raise ValidationError("Colonne manquante : " + ", ".join(manquantes) + ". Colonnes attendues : code, désignation, "
                              "unité, quantité, puis au besoin seuil, rangement, prix.")

    unites = {_cle(u.code): u for u in Unite.objects.all()}
    bilan = {"lues": 0, "articles_crees": 0, "stocks_modifies": 0, "inchanges": 0, "erreurs": [], "simulation": simuler}
    vus = set()
    with transaction.atomic():
        verrouiller()
        for n, ligne in enumerate(lignes, start=2):
            def lire(nom):
                return ligne[col[nom]] if col[nom] is not None and col[nom] < len(ligne) else None

            code = str(lire("code") or "").strip()
            if not code and not lire("designation"):
                continue
            bilan["lues"] += 1
            if bilan["lues"] > LIGNES_MAX:
                raise ValidationError(f"Trop de lignes : {LIGNES_MAX} au plus par fichier.")
            try:
                if not code:
                    raise ValueError("code manquant")
                if code.lower() in vus:
                    raise ValueError(f"le code {code} figure deux fois")
                vus.add(code.lower())
                quantite = _nombre(lire("quantite"), "quantité")
                if quantite is None:
                    raise ValueError("quantité manquante")
                seuil, prix = _nombre(lire("seuil"), "seuil"), _nombre(lire("prix"), "prix")
                casier = str(lire("casier") or "").strip()[:40]
                article = Article.objects.filter(code__iexact=code).first()
                if article is None:
                    designation = str(lire("designation") or "").strip()
                    if not designation:
                        raise ValueError("désignation manquante pour un article nouveau")
                    unite = unites.get(_cle(lire("unite") or "U"))
                    if unite is None:
                        raise ValueError(f"unité inconnue (« {lire('unite')} »)")
                    article = Article.objects.create(code=code[:30], designation=designation[:200], unite=unite,
                                                     cree_par=utilisateur, modifie_par=utilisateur)
                    bilan["articles_crees"] += 1
                elif not article.gere_en_stock:
                    raise ValueError("cet article n'est pas géré en stock")
                ecart = quantite - quantite_en_stock(article, magasin)
                if ecart:
                    Mouvement.objects.create(article=article, magasin=magasin, type=Mouvement.Type.INVENTAIRE, quantite=ecart,
                                             prix_unitaire=prix, motif="Import du stock depuis Excel", auteur=utilisateur)
                    bilan["stocks_modifies"] += 1
                else:
                    bilan["inchanges"] += 1
                if seuil is not None or casier:
                    reglage, _ = ReglageStock.objects.get_or_create(article=article, magasin=magasin)
                    reglage.seuil_mini = seuil if seuil is not None else reglage.seuil_mini
                    reglage.casier = casier or reglage.casier
                    reglage.save()
            except ValueError as e:
                bilan["erreurs"].append(f"Ligne {n} : {e}.")
        if simuler or bilan["erreurs"]:
            transaction.set_rollback(True)
    bilan["erreurs"] = bilan["erreurs"][:50]
    bilan["ecrit"] = not simuler and not bilan["erreurs"]
    return bilan
