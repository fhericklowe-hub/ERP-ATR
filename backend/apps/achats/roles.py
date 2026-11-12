"""Rôles par défaut du module Achats. Ils restent modifiables dans l'administration."""

# Listes nécessaires pour remplir une demande.
LECTURE = ["core.view_site", "core.view_service", "referentiels.view_unite", "referentiels.view_article"]
COMMANDE = [
    "achats.view_boncommande", "achats.add_boncommande", "achats.change_boncommande",
    "referentiels.view_tiers", "referentiels.add_tiers", "referentiels.change_tiers",
]
SAISIE = ["achats.view_demandeachat", "achats.add_demandeachat", "achats.change_demandeachat"]

ROLES = {
    "Achats - Demandeur": LECTURE + SAISIE,
    "Achats - Directeur technique": LECTURE + [
        "achats.view_demandeachat", "achats.voir_toutes_demandeachat",
        "achats.valider_direction_technique_demandeachat",
    ],
    "Achats - Acheteur": LECTURE + SAISIE + COMMANDE + ["achats.voir_toutes_demandeachat", "achats.view_acheteur"],
    "Achats - Contrôleur de gestion": LECTURE + [
        "achats.view_demandeachat", "achats.voir_toutes_demandeachat",
        "achats.view_boncommande", "achats.valider_controle_boncommande",
    ],
    "Achats - Responsable achats": LECTURE + SAISIE + COMMANDE + [
        "achats.valider_responsable_boncommande",
        "achats.voir_toutes_demandeachat", "achats.valider_achats_demandeachat",
        "achats.view_acheteur", "achats.change_acheteur",
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
