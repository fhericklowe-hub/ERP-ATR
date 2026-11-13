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
