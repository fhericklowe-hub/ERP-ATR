from django.utils import timezone


def actions(utilisateur):
    """Actions correctives confiées à cette personne, en retard ou à faire dans les 7 jours."""
    from .models import ActionCorrective

    if not utilisateur.has_perm("hse.view_actioncorrective"):
        return None
    aujourd_hui, lignes = timezone.localdate(), []
    for a in ActionCorrective.objects.filter(responsable=utilisateur, statut=ActionCorrective.Statut.A_FAIRE).select_related("evenement"):
        jours = (a.echeance - aujourd_hui).days
        if jours <= 7:
            quand = f"en retard de {-jours} jour(s)" if jours < 0 else "aujourd'hui" if jours == 0 else f"dans {jours} jour(s)"
            lignes.append(f"{a.evenement.numero} : {a.description}, avant le {a.echeance:%d/%m/%Y} ({quand})")
    return "Actions correctives HSE", lignes


def evenements(utilisateur):
    """Pour le responsable HSE : les déclarations qui attendent leur analyse."""
    from .models import Evenement

    if not utilisateur.has_perm("hse.traiter_evenement"):
        return None
    return "Événements HSE à analyser", [
        f"{e.numero} : {e.get_type_display()} du {timezone.localtime(e.date):%d/%m/%Y}, {e.site.nom}"
        for e in Evenement.objects.filter(statut=Evenement.Statut.DECLARE).select_related("site").order_by("date")]
