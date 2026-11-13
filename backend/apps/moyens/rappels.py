from django.utils import timezone


def echeances(utilisateur):
    """Échéances en retard ou dans leur délai de rappel, pour ceux qui les traitent."""
    from .contrats import Echeance

    if not utilisateur.has_perm("moyens.change_echeance"):
        return None
    aujourdhui, lignes = timezone.localdate(), []
    for e in Echeance.objects.filter(statut=Echeance.Statut.A_FAIRE).order_by("date_echeance"):
        jours = (e.date_echeance - aujourdhui).days
        if jours < 0:
            lignes.append(f"{e.libelle} : en retard de {-jours} jour(s) (échéance du {e.date_echeance:%d/%m/%Y})")
        elif jours <= e.rappel_jours:
            lignes.append(f"{e.libelle} : le {e.date_echeance:%d/%m/%Y}" + (" (aujourd'hui)" if jours == 0 else f" (dans {jours} jour(s))"))
    return "Échéances des moyens généraux", lignes


# Où traiter chaque rubrique dans l'application (page d'accueil).
echeances.lien = "/echeances"
