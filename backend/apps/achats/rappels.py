"""Ce qui attend une personne aux Achats : les demandes et les bons de commande qu'elle doit valider ou traiter."""


def demandes_a_valider(utilisateur):
    """Demandes d'achat en attente de cette personne : responsable de service, directeur technique, achats."""
    from .models import DemandeAchat

    if not utilisateur.has_perm("achats.view_demandeachat"):
        return None
    S = DemandeAchat.Statut
    en_attente = DemandeAchat.objects.filter(statut__in=[S.ATTENTE_SERVICE, S.ATTENTE_DT, S.ATTENTE_ACHATS]) \
        .select_related("service", "demandeur", "acheteur").order_by("urgence", "cree_le")
    lignes = []
    for d in en_attente:
        a_moi = d.peut_valider(utilisateur) or (d.statut == S.ATTENTE_ACHATS and d.acheteur_id == utilisateur.id)
        if a_moi:
            lignes.append(f"{d.numero} : {d.service}, demandée par {d.demandeur} ({d.get_statut_display().lower()})")
    return "Demandes d'achat à traiter", lignes


def commandes_a_valider(utilisateur):
    """Bons de commande qui attendent la validation de cette personne (responsable achats, contrôleur de gestion)."""
    from .commande import BonCommande

    if not utilisateur.has_perm("achats.view_boncommande"):
        return None
    S = BonCommande.Statut
    bons = BonCommande.objects.filter(statut__in=[S.ATTENTE_RESPONSABLE, S.ATTENTE_CONTROLE]).select_related("fournisseur").order_by("cree_le")
    return "Bons de commande à valider", [f"{b.numero} : {b.fournisseur}" for b in bons if b.peut_valider(utilisateur)]


demandes_a_valider.lien = "/"
commandes_a_valider.lien = "/commandes"
