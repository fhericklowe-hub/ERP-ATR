def entretiens(utilisateur):
    """Entretiens préventifs à faire ou bientôt à faire, sans OR déjà ouvert, pour le chef d'atelier."""
    from .entretien import PlanEntretien
    from .models import Materiel

    if not utilisateur.has_perm("technique.piloter_ordrereparation"):
        return None
    S, a_faire, bientot = PlanEntretien.Situation, [], []
    plans = PlanEntretien.objects.filter(actif=True).exclude(materiel__etat=Materiel.Etat.REFORME).select_related("materiel")
    for p in plans:
        if p.situation == S.A_VENIR or p.ordre_en_cours():
            continue
        (a_faire if p.situation == S.RETARD else bientot).append(
            f"{p.materiel.code} · {p.intitule} : {'à faire' if p.situation == S.RETARD else 'bientôt'}")
    return "Entretiens préventifs", a_faire + bientot


def ordres_a_cloturer(utilisateur):
    from .models import OrdreReparation

    if not utilisateur.has_perm("technique.piloter_ordrereparation"):
        return None
    ordres = OrdreReparation.objects.filter(statut=OrdreReparation.Statut.TERMINE).select_related("materiel").order_by("termine_le")
    return "Ordres de réparation terminés, à clôturer", [f"{o.numero} · {o.materiel.code}" for o in ordres]


# Où traiter chaque rubrique dans l'application (page d'accueil).
entretiens.lien = "/entretien"
ordres_a_cloturer.lien = "/ordres"
