"""Rôles par défaut du stock. Ils restent modifiables dans l'administration."""

LECTURE = ["core.view_site", "core.view_service", "core.view_utilisateur", "referentiels.view_unite",
           "referentiels.view_article", "referentiels.view_emplacement", "stock.view_mouvement",
           "stock.view_reglagestock", "stock.view_bonsortie"]
SORTIE = ["stock.add_bonsortie", "stock.change_bonsortie"]
DEMANDE = ["stock.view_demandesortie", "stock.add_demandesortie", "stock.change_demandesortie"]

ROLES = {
    # Tout salarié qui demande des pièces pour un OR ou des fournitures pour son service.
    "Stock - Demandeur": ["core.view_site", "core.view_service", "referentiels.view_unite", "referentiels.view_article",
                          "referentiels.view_emplacement"] + DEMANDE,
    "Stock - Consultation": LECTURE + ["stock.view_demandesortie"],
    "Stock - Magasinier": LECTURE + SORTIE + DEMANDE,
    "Stock - Responsable": LECTURE + SORTIE + DEMANDE + [
        "stock.ajuster_stock", "stock.annuler_bonsortie", "stock.add_reglagestock", "stock.change_reglagestock",
    ],
}


def creer_roles(sender, **kwargs):
    from django.contrib.auth.models import Group, Permission
    from django.db.models import Q

    for nom, droits in ROLES.items():
        groupe, cree = Group.objects.get_or_create(name=nom)
        if not cree:  # on ne touche pas à un rôle déjà ajusté par l'administrateur
            continue
        filtre = Q()
        for droit in droits:
            app, code = droit.split(".")
            filtre |= Q(content_type__app_label=app, codename=code)
        groupe.permissions.set(Permission.objects.filter(filtre))


# Droits ajoutés avec les demandes de sortie, pour les rôles créés avant.
DROITS_DEMANDES = {"Stock - Consultation": ["stock.view_demandesortie"], "Stock - Magasinier": DEMANDE,
                   "Stock - Responsable": DEMANDE}
