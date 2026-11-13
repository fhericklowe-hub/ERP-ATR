def echeances_du_personnel(utilisateur):
    """Pièces à renouveler et fins de contrat dans les 30 jours, pour les gestionnaires RH."""
    from .models import echeances

    if not utilisateur.has_perm("rh.change_salarie"):
        return None
    lignes = []
    for e in echeances():
        quand = f"dépassé depuis {-e['jours']} jour(s)" if e["jours"] < 0 else "aujourd'hui" if e["jours"] == 0 else f"dans {e['jours']} jour(s)"
        lignes.append(f"{e['salarie_nom']} ({e['matricule']}) : {e['libelle']}, le {e['date']:%d/%m/%Y} ({quand})")
    return "Échéances du personnel", lignes


def absences_a_traiter(utilisateur):
    """Demandes d'absence qui attendent l'accord de cette personne : son équipe, et toutes pour les RH."""
    from django.db.models import Q

    from .conges import DemandeAbsence

    if not utilisateur.has_perm("rh.view_demandeabsence"):
        return None
    S = DemandeAbsence.Statut
    filtre = Q(statut=S.SOUMISE) & (Q(salarie__responsable__utilisateur=utilisateur) | Q(salarie__service__responsable=utilisateur))
    if utilisateur.has_perm("rh.approuver_demandeabsence"):
        filtre |= Q(statut=S.VISEE)
    demandes = DemandeAbsence.objects.filter(filtre).exclude(salarie__utilisateur=utilisateur).select_related("salarie").order_by("date_debut")
    return "Demandes d'absence à traiter", [
        f"{d.numero} : {d.salarie}, {d.get_type_display().lower()} du {d.date_debut:%d/%m/%Y} au {d.date_fin:%d/%m/%Y} ({d.jours:n} j)" for d in demandes]
