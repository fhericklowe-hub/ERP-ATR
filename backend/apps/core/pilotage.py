"""Tableau de bord de direction : quelques chiffres par module, calculés à la demande.

Chaque fonction renvoie (module, adresse de l'écran, [(libellé, valeur, alerte)]). « Du mois » : le mois civil en cours."""
import datetime
from decimal import Decimal

from django.utils import timezone


def _fcfa(montant) -> str:
    return f"{Decimal(montant or 0):,.0f}".replace(",", " ") + " FCFA"


def _debut_du_mois() -> datetime.date:
    return timezone.localdate().replace(day=1)


def achats():
    from apps.achats.commande import BonCommande
    from apps.achats.models import DemandeAchat

    D, B = DemandeAchat.Statut, BonCommande.Statut
    en_attente = DemandeAchat.objects.filter(statut__in=[D.ATTENTE_SERVICE, D.ATTENTE_DT, D.ATTENTE_ACHATS])
    en_retard = en_attente.filter(statut=D.ATTENTE_ACHATS, echeance_commande__lt=timezone.now()).count()
    du_mois = BonCommande.objects.filter(date__gte=_debut_du_mois()).exclude(statut__in=[B.BROUILLON, B.ANNULE]).prefetch_related("lignes")
    total, sans_cours = Decimal(0), 0
    for bon in du_mois:
        valeur = bon.totaux()["contre_valeur_xof"]
        total += valeur or 0
        sans_cours += valeur is None
    a_valider = BonCommande.objects.filter(statut__in=[B.ATTENTE_RESPONSABLE, B.ATTENTE_CONTROLE]).count()
    return "Achats", "/commandes", [
        ("Demandes d'achat en cours de circuit", str(en_attente.count()), False),
        ("Demandes hors délai aux achats", str(en_retard), en_retard > 0),
        ("Bons de commande à valider", str(a_valider), False),
        ("Commandé ce mois (TTC)", _fcfa(total) + (f" (hors {sans_cours} bon(s) en devise sans cours)" if sans_cours else ""), False),
        ("Bons de commande du mois", str(len(du_mois)), False),
    ]


def stock():
    from django.db.models import Sum

    from apps.stock.models import Mouvement, ReglageStock
    from apps.stock.valorisation import valeur_du_stock

    valeur = valeur_du_stock()
    quantites = {(m["article"], m["magasin"]): m["q"] for m in Mouvement.objects.values("article", "magasin").annotate(q=Sum("quantite"))}
    sous_seuil = sum(1 for r in ReglageStock.objects.filter(seuil_mini__gt=0, article__actif=True)
                     if quantites.get((r.article_id, r.magasin_id), 0) <= r.seuil_mini)
    return "Stock", "/stock/valeur", [
        ("Valeur du stock (coût moyen)", _fcfa(valeur["total"]), False),
        ("Articles en stock", str(len({l["article"] for l in valeur["lignes"]})), False),
        ("Articles au seuil d'alerte ou en dessous", str(sous_seuil), sous_seuil > 0),
    ]


def technique():
    from apps.technique.models import Materiel, OrdreReparation

    E, S = Materiel.Etat, OrdreReparation.Statut
    parc = Materiel.objects.exclude(etat=E.REFORME)
    total = parc.count()
    arretes = parc.filter(etat__in=[E.EN_PANNE, E.EN_REPARATION]).count()
    return "Technique", "/parc", [
        ("Matériels au parc", str(total), False),
        ("En exploitation ou en location", str(parc.filter(etat=E.EN_EXPLOITATION).count()), False),
        ("En panne ou en réparation", f"{arretes}" + (f" ({arretes * 100 // total} %)" if total else ""), arretes > 0),
        ("Ordres de réparation ouverts", str(OrdreReparation.objects.filter(statut__in=[S.OUVERT, S.EN_COURS, S.TERMINE]).count()), False),
    ]


def commercial():
    from apps.commercial.models import Devis
    from apps.exploitation.models import MiseADisposition

    S = Devis.Statut
    du_mois = Devis.objects.filter(date__gte=_debut_du_mois()).exclude(statut__in=[S.BROUILLON, S.ANNULE]).prefetch_related("lignes")
    acceptes = [d for d in du_mois if d.statut == S.ACCEPTE]
    return "Commercial et Exploitation", "/devis", [
        ("Devis émis ce mois", str(len(du_mois)), False),
        ("Montant des devis du mois (HT)", _fcfa(sum(d.totaux()["total_ht"] for d in du_mois)), False),
        ("Devis acceptés ce mois", f"{len(acceptes)} · {_fcfa(sum(d.totaux()['total_ht'] for d in acceptes))} HT", False),
        ("Matériels chez les clients", str(MiseADisposition.objects.filter(statut=MiseADisposition.Statut.EN_COURS).count()), False),
    ]


def personnel():
    from apps.rh.conges import DemandeAbsence
    from apps.rh.models import Salarie, echeances

    aujourd_hui = timezone.localdate()
    absents = DemandeAbsence.objects.filter(statut=DemandeAbsence.Statut.APPROUVEE, date_debut__lte=aujourd_hui, date_fin__gte=aujourd_hui)
    depassees = sum(1 for e in echeances() if e["jours"] < 0)
    return "Personnel", "/personnel", [
        ("Salariés en poste", str(Salarie.objects.filter(statut=Salarie.Statut.ACTIF).count()), False),
        ("Absents aujourd'hui", str(absents.values("salarie").distinct().count()), False),
        ("Pièces du personnel échues (permis, visites médicales…)", str(depassees), depassees > 0),
    ]


def hse():
    from apps.hse.models import indicateurs

    i = indicateurs()
    sans = i["jours_sans_accident"]
    return "HSE", "/hse", [
        ("Jours sans accident avec arrêt", "aucun accident enregistré" if sans is None else str(sans), False),
        (f"Événements déclarés en {i['annee']}", str(i["total"]), False),
        (f"Accidents avec arrêt en {i['annee']}", f"{i['accidents_avec_arret']} · {i['jours_arret']} jour(s) d'arrêt", i["accidents_avec_arret"] > 0),
        ("Actions correctives en retard", str(i["actions_en_retard"]), i["actions_en_retard"] > 0),
    ]


def moyens_generaux():
    from apps.moyens.models import DemandeIntervention

    S = DemandeIntervention.Statut
    return "Moyens généraux", "/interventions", [
        ("Demandes d'intervention en cours", str(DemandeIntervention.objects.filter(statut__in=[S.NOUVELLE, S.PRISE_EN_CHARGE]).count()), False),
    ]


SOURCES = [achats, stock, technique, commercial, personnel, hse, moyens_generaux]


def tableau() -> list:
    resultat = []
    for source in SOURCES:
        module, lien, lignes = source()
        resultat.append({"module": module, "lien": lien,
                         "indicateurs": [{"libelle": libelle, "valeur": valeur, "alerte": alerte} for libelle, valeur, alerte in lignes]})
    return resultat
