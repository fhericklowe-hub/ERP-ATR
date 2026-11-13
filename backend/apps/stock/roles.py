"""Rôles par défaut du stock. Ils restent modifiables dans l'administration."""

LECTURE = ["core.view_site", "core.view_service", "core.view_utilisateur", "referentiels.view_unite",
           "referentiels.view_article", "referentiels.view_emplacement", "stock.view_mouvement",
           "stock.view_reglagestock", "stock.view_bonsortie"]
SORTIE = ["stock.add_bonsortie", "stock.change_bonsortie"]
# Tenir le catalogue des articles : créer, corriger, désactiver.
CATALOGUE = ["referentiels.add_article", "referentiels.change_article", "referentiels.view_famillearticle"]
DEMANDE = ["stock.view_demandesortie", "stock.add_demandesortie", "stock.change_demandesortie"]

ROLES = {
    # Tout salarié qui demande des pièces pour un OR ou des fournitures pour son service.
    "Stock - Demandeur": ["core.view_site", "core.view_service", "referentiels.view_unite", "referentiels.view_article",
                          "referentiels.view_emplacement"] + DEMANDE,
    "Stock - Consultation": LECTURE + ["stock.view_demandesortie"],
    "Stock - Magasinier": LECTURE + SORTIE + DEMANDE,
    "Stock - Responsable": LECTURE + SORTIE + DEMANDE + CATALOGUE + [
        "stock.ajuster_stock", "stock.voir_valeur_stock", "stock.annuler_bonsortie", "stock.add_reglagestock", "stock.change_reglagestock",
    ],
}


def creer_roles(sender, **kwargs):
    from django.contrib.auth.models import Group, Permission
    from django.db.models import Q

    def droits_de(droits):
        filtre = Q()
        for droit in droits:
            app, code = droit.split(".")
            filtre |= Q(content_type__app_label=app, codename=code)
        return Permission.objects.filter(filtre)

    premiere_fois = not Group.objects.filter(name__in=ROLES).exists()
    for nom, droits in ROLES.items():
        groupe, cree = Group.objects.get_or_create(name=nom)
        if cree:  # on ne touche pas à un rôle déjà ajusté par l'administrateur
            groupe.permissions.set(droits_de(droits))
    if premiere_fois:  # à l'installation seulement : les droits donnés aux rôles des achats
        for nom, droits in [*DROITS_VALEUR.items(), *DROITS_CATALOGUE.items()]:
            groupe = Group.objects.filter(name=nom).first()
            if groupe:
                groupe.permissions.add(*droits_de(droits))


# Droits ajoutés avec les demandes de sortie, pour les rôles créés avant.
DROITS_DEMANDES = {"Stock - Consultation": ["stock.view_demandesortie"], "Stock - Magasinier": DEMANDE,
                   "Stock - Responsable": DEMANDE}
# Droit ajouté avec la valorisation du stock, pour les rôles créés avant.
DROITS_VALEUR = {"Stock - Responsable": ["stock.voir_valeur_stock"], "Achats - Contrôleur de gestion": ["stock.voir_valeur_stock"],
                 "Achats - Responsable achats": ["stock.voir_valeur_stock"]}
# Droits ajoutés avec l'écran du catalogue des articles, pour les rôles créés avant.
DROITS_CATALOGUE = {"Stock - Responsable": CATALOGUE, "Achats - Acheteur": CATALOGUE, "Achats - Responsable achats": CATALOGUE}
