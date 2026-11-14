"""Import du stock de départ (ou d'un inventaire complet) depuis un classeur Excel.

Première feuille ; les titres des colonnes sont sur la première ligne utile (quelques lignes au-dessus sont tolérées).
Colonnes reconnues, dans n'importe quel ordre : code (ou référence), désignation, unité, quantité (obligatoires sauf
unité), seuil, rangement, prix (ou PMP).
Les articles inconnus sont créés. Le stock du magasin est mis à la quantité du fichier.

Export d'un logiciel de stock : si le classeur a une colonne « Succursale » (et au besoin « Constructeur »), chaque
succursale est associée à un magasin ; les lignes d'un même article (plusieurs entrées en stock) sont additionnées, le prix
est le prix moyen pondéré (valeur du stock / quantité) et le code de l'article est « CONSTRUCTEUR-RÉFÉRENCE »."""
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from itertools import islice

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from openpyxl import load_workbook

from apps.referentiels.models import Article, Unite

from .models import Mouvement, ReglageStock, exiger_magasin, quantite_en_stock, verrouiller

COLONNES = {
    "code": ("code", "code article", "reference", "ref"),
    "succursale": ("succursale", "code succ", "succ"),
    "constructeur": ("constructeur", "code constructeur"),
    "valeur": ("val stk", "valeur", "valeur stock", "valeur du stock"),
    "designation": ("designation", "libelle", "article"),
    "unite": ("unite", "u"),
    "quantite": ("quantite", "qte", "stock", "quantite en stock"),
    "seuil": ("seuil", "seuil mini", "seuil d'alerte", "stock mini"),
    "casier": ("rangement", "casier", "emplacement"),
    "prix": ("prix", "prix unitaire", "pu", "pmp", "pmp du stock"),
}
LIGNES_MAX = 5000
LIGNES_TITRES = 20


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


def _titre(cellule) -> str:
    return _cle(re.sub(r"\([^)]*\)", " ", str(cellule or "")))


def importer(utilisateur, fichier, magasin=None, simuler=False, succursales=None) -> dict:
    """Lit le classeur et met le stock à jour. Avec `simuler`, rien n'est écrit : on obtient le compte rendu.
    S'il y a une seule ligne en erreur, rien n'est écrit non plus.

    `magasin` : le magasin du stock, pour un classeur sans colonne « Succursale ».
    `succursales` : {code de succursale : magasin}, pour un classeur qui en a une."""
    if not utilisateur.has_perm("stock.ajuster_stock"):
        raise PermissionDenied("Seul le responsable du stock peut importer un stock.")
    if magasin is not None:
        exiger_magasin(magasin)
    succursales = {str(k).strip().upper(): v for k, v in (succursales or {}).items()}
    for m in succursales.values():
        exiger_magasin(m)
    try:
        feuille = load_workbook(fichier, data_only=True, read_only=True).worksheets[0]
        toutes = list(feuille.iter_rows(values_only=True))
    except Exception:
        raise ValidationError("Fichier illisible : il faut un classeur Excel (.xlsx).")
    if not toutes:
        raise ValidationError("Le classeur est vide.")
    # La ligne des titres est la première, parmi les premières lignes, qui a une colonne de code et une de quantité.
    def titres_de(l):
        return [_titre(c) for c in l]

    entete = next((i for i, l in enumerate(islice(toutes, LIGNES_TITRES))
                   if any(t in COLONNES["code"] for t in titres_de(l)) and any(t in COLONNES["quantite"] for t in titres_de(l))), 0)
    titres = titres_de(toutes[entete])
    col = {nom: next((titres.index(t) for t in variantes if t in titres), None) for nom, variantes in COLONNES.items()}
    manquantes = [n for n in ("code", "designation", "quantite") if col[n] is None]
    if manquantes:
        raise ValidationError("Colonne manquante : " + ", ".join(manquantes) + ". Colonnes attendues : code, désignation, "
                              "unité, quantité, puis au besoin seuil, rangement, prix.")
    par_succursale = col["succursale"] is not None
    if not par_succursale and magasin is None:
        raise ValidationError("Choisissez le magasin.")

    # Lecture : une entrée par (succursale, code d'article) ; plusieurs lignes d'un même article sont additionnées.
    bilan = {"lues": 0, "articles_crees": 0, "stocks_modifies": 0, "inchanges": 0, "erreurs": [], "simulation": simuler,
             "avertissements": [], "succursales": []}
    erreurs_lecture, articles, associe = [], {}, True
    for n, ligne in enumerate(toutes[entete + 1:], start=entete + 2):
        def lire(nom):
            return ligne[col[nom]] if col[nom] is not None and col[nom] < len(ligne) else None

        reference = str(lire("code") or "").strip()
        if not reference and not lire("designation"):
            continue
        bilan["lues"] += 1
        if bilan["lues"] > LIGNES_MAX * 10:
            raise ValidationError(f"Trop de lignes : {LIGNES_MAX * 10} au plus par fichier.")
        try:
            if not reference:
                raise ValueError("code manquant")
            constructeur = str(lire("constructeur") or "").strip()
            code = f"{constructeur}-{reference}" if constructeur else reference
            succ = str(lire("succursale") or "").strip().upper() if par_succursale else ""
            if par_succursale and not succ:
                raise ValueError("succursale manquante")
            quantite = _nombre(lire("quantite"), "quantité")
            if quantite is None:
                raise ValueError("quantité manquante")
            prix = valeur = None
            try:
                prix, valeur = _nombre(lire("prix"), "prix"), _nombre(lire("valeur"), "valeur")
            except ValueError as err:
                if "négatif" not in str(err):
                    raise
                # un prix négatif est une erreur du fichier d'origine : l'article entre en stock sans ce prix
                bilan["avertissements"].append(f"Ligne {n} : {err}, prix ignoré.")
            e = articles.setdefault((succ, code.lower()), {"n": n, "succ": succ, "code": code, "quantite": Decimal(0), "valeur": Decimal(0),
                                                           "avec_valeur": False, "prix": prix, "casier": "", "casier_qte": Decimal(-1),
                                                           "designation": "", "unite": lire("unite"), "seuil": None, "lots": 0})
            if not par_succursale and e["lots"]:
                raise ValueError(f"le code {code} figure deux fois")
            e["lots"] += 1
            e["quantite"] += quantite
            if valeur is not None:
                e["valeur"] += valeur
                e["avec_valeur"] = True
            elif prix is not None:
                e["valeur"] += prix * quantite
                e["avec_valeur"] = True
            e["designation"] = e["designation"] or str(lire("designation") or "").strip()
            casier = str(lire("casier") or "").strip()[:40]
            if casier and quantite > e["casier_qte"]:   # le rangement principal est celui où il y a le plus de pièces
                e["casier"], e["casier_qte"] = casier, quantite
            seuil = _nombre(lire("seuil"), "seuil")
            e["seuil"] = seuil if seuil is not None else e["seuil"]
        except ValueError as err:
            erreurs_lecture.append(f"Ligne {n} : {err}.")
    if bilan["lues"] > LIGNES_MAX and not par_succursale:
        raise ValidationError(f"Trop de lignes : {LIGNES_MAX} au plus par fichier.")
    bilan["erreurs"] += erreurs_lecture
    if par_succursale:
        for succ in sorted({e["succ"] for e in articles.values()}):
            lots = [e for e in articles.values() if e["succ"] == succ]
            bilan["succursales"].append({"code": succ, "articles": len(lots), "quantite": sum(e["quantite"] for e in lots),
                                         "magasin": succursales[succ].id if succ in succursales else None})
        manquantes = [x["code"] for x in bilan["succursales"] if x["magasin"] is None]
        associe = not manquantes
        if manquantes:
            bilan["erreurs"].append("Associez à un magasin chaque succursale du fichier : " + ", ".join(manquantes) + ".")

    unites = {_cle(u.code): u for u in Unite.objects.all()}
    with transaction.atomic():
        verrouiller()
        if associe:
            for e in articles.values():
                try:
                    cible = succursales[e["succ"]] if par_succursale else magasin
                    if len(e["code"]) > 30:
                        raise ValueError(f"code trop long (30 caractères au plus) : {e['code']}")
                    # prix moyen pondéré : valeur du stock / quantité
                    prix = (e["valeur"] / e["quantite"]).quantize(Decimal("0.01")) if e["avec_valeur"] and e["quantite"] else e["prix"]
                    article = Article.objects.filter(code__iexact=e["code"]).first()
                    if article is None:
                        if not e["designation"]:
                            raise ValueError("désignation manquante pour un article nouveau")
                        unite = unites.get(_cle(e["unite"] or "U"))
                        if unite is None:
                            raise ValueError(f"unité inconnue (« {e['unite']} »)")
                        article = Article.objects.create(code=e["code"], designation=e["designation"][:200], unite=unite,
                                                         cree_par=utilisateur, modifie_par=utilisateur)
                        bilan["articles_crees"] += 1
                    elif not article.gere_en_stock:
                        raise ValueError("cet article n'est pas géré en stock")
                    ecart = e["quantite"] - quantite_en_stock(article, cible)
                    if ecart:
                        Mouvement.objects.create(article=article, magasin=cible, type=Mouvement.Type.INVENTAIRE, quantite=ecart,
                                                 prix_unitaire=prix, motif="Import du stock depuis Excel", auteur=utilisateur)
                        bilan["stocks_modifies"] += 1
                    else:
                        bilan["inchanges"] += 1
                    if e["seuil"] is not None or e["casier"]:
                        reglage, _ = ReglageStock.objects.get_or_create(article=article, magasin=cible)
                        reglage.seuil_mini = e["seuil"] if e["seuil"] is not None else reglage.seuil_mini
                        reglage.casier = e["casier"] or reglage.casier
                        reglage.save()
                except ValueError as err:
                    bilan["erreurs"].append(f"Ligne {e['n']} : {err}.")
        if simuler or bilan["erreurs"]:
            transaction.set_rollback(True)
    bilan["erreurs"] = bilan["erreurs"][:50]
    bilan["avertissements"] = bilan["avertissements"][:50]
    bilan["ecrit"] = not simuler and not bilan["erreurs"]
    bilan["succursales"] = [{**x, "quantite": str(x["quantite"])} for x in bilan["succursales"]]
    return bilan
