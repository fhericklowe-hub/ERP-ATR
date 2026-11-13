"""Valorisation du stock au coût moyen unitaire pondéré (CMUP).

Le coût moyen d'un article est celui de toute l'entreprise : chaque entrée avec un prix (bon de réception, stock de
départ, ajustement chiffré) le recalcule, chaque sortie se fait à ce coût. Une entrée sans prix entre au coût moyen
du moment. Un transfert entre magasins ne change pas le coût. Rien n'est stocké : tout est recalculé à partir des
mouvements, ce qui donne aussi la valeur du stock à une date passée."""
import datetime
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone

from apps.core.devises import arrondi

from .models import Mouvement

ZERO = Decimal(0)
CENTIME = Decimal("0.01")


def _fin_de_journee(jour: datetime.date):
    return timezone.make_aware(datetime.datetime.combine(jour + datetime.timedelta(days=1), datetime.time.min))


def rejouer(jusqu_au: datetime.date | None = None, sorties_depuis: datetime.date | None = None):
    """Rejoue les mouvements dans l'ordre. Renvoie (quantités par (article, magasin), coût moyen par article,
    sorties valorisées). Une sortie valorisée : (ligne de bon de sortie, magasin, quantité sortie, coût unitaire ou
    None s'il n'est pas connu) ; une sortie annulée revient en négatif."""
    mouvements = Mouvement.objects.order_by("date", "id")
    if jusqu_au:
        mouvements = mouvements.filter(date__lt=_fin_de_journee(jusqu_au))
    debut = timezone.make_aware(datetime.datetime.combine(sorties_depuis, datetime.time.min)) if sorties_depuis else None
    par_magasin, total, cmup, sorties = defaultdict(lambda: ZERO), defaultdict(lambda: ZERO), {}, []
    T = Mouvement.Type
    for article, magasin, date, type_, quantite, prix, ligne_sortie in mouvements.values_list(
            "article_id", "magasin_id", "date", "type", "quantite", "prix_unitaire", "ligne_sortie_id").iterator():
        par_magasin[article, magasin] += quantite
        if type_ == T.TRANSFERT:
            continue
        avant = total[article]
        total[article] = avant + quantite
        if quantite > 0 and type_ in (T.RECEPTION, T.INVENTAIRE) and prix is not None:
            connu = cmup.get(article)
            cmup[article] = prix if connu is None or avant <= 0 else (avant * connu + quantite * prix) / (avant + quantite)
        if ligne_sortie and type_ in (T.SORTIE, T.ANNULATION) and (debut is None or date >= debut):
            sorties.append((ligne_sortie, magasin, -quantite, cmup.get(article)))
    return par_magasin, cmup, sorties


def valeur_du_stock(jusqu_au=None, magasin=None, recherche="") -> dict:
    """Une ligne par article et par magasin encore en stock, avec sa valeur au coût moyen."""
    from apps.referentiels.models import Article, Emplacement

    quantites, cmup, _ = rejouer(jusqu_au)
    cles = [c for c, q in quantites.items() if q != 0 and (magasin is None or c[1] == magasin)]
    articles = Article.objects.filter(id__in={c[0] for c in cles}).select_related("unite")
    if recherche:
        from django.db.models import Q
        articles = articles.filter(Q(code__icontains=recherche) | Q(designation__icontains=recherche))
    articles = {a.id: a for a in articles}
    magasins = dict(Emplacement.objects.filter(id__in={c[1] for c in cles}).values_list("id", "nom"))
    lignes, total, sans_prix = [], ZERO, 0
    for article_id, magasin_id in cles:
        a = articles.get(article_id)
        if not a:
            continue
        quantite, cout = quantites[article_id, magasin_id], cmup.get(article_id)
        valeur = None if cout is None else arrondi(quantite * cout)
        total += valeur or ZERO
        sans_prix += cout is None
        lignes.append({"article": a.id, "code": a.code, "designation": a.designation, "nature": a.get_nature_display(),
                       "unite": a.unite.code, "magasin": magasin_id, "magasin_nom": magasins[magasin_id], "quantite": quantite,
                       "cout_moyen": None if cout is None else cout.quantize(CENTIME, rounding=ROUND_HALF_UP), "valeur": valeur})
    lignes.sort(key=lambda l: (l["designation"].lower(), l["magasin_nom"]))
    return {"lignes": lignes, "total": total, "sans_prix": sans_prix}


def consommations(debut: datetime.date, fin: datetime.date, magasin=None) -> dict:
    """Valeur de ce qui est sorti du stock sur la période (bons de sortie, annulations déduites), par service et par OR."""
    from .models import LigneBonSortie

    _, _, sorties = rejouer(fin, debut)
    sorties = [s for s in sorties if magasin is None or s[1] == magasin]
    lignes = {l.id: l for l in LigneBonSortie.objects.filter(id__in={s[0] for s in sorties}).select_related("bon__service")}
    par_service, par_or, total, sans_prix = defaultdict(lambda: ZERO), {}, ZERO, 0
    for ligne_id, _, quantite, cout in sorties:
        bon = lignes[ligne_id].bon
        if cout is None:
            sans_prix += quantite > 0
            continue
        valeur = quantite * cout
        total += valeur
        par_service[bon.service.nom if bon.service_id else "Sans service"] += valeur
        if bon.numero_or:
            ligne = par_or.setdefault(bon.numero_or, {"numero_or": bon.numero_or, "materiel": bon.materiel, "valeur": ZERO})
            ligne["valeur"] += valeur
            ligne["materiel"] = ligne["materiel"] or bon.materiel

    def trier(valeurs, cle):
        return sorted(({**v, "valeur": arrondi(v["valeur"])} for v in valeurs if arrondi(v["valeur"]) != 0), key=lambda v: (-v["valeur"], v[cle]))

    return {"total": arrondi(total), "sans_prix": sans_prix,
            "par_service": trier(({"service": nom, "valeur": v} for nom, v in par_service.items()), "service"),
            "par_or": trier(par_or.values(), "numero_or")}
