"""Rôles par défaut du module Achats. Ils restent modifiables dans l'administration."""

# Listes nécessaires pour remplir une demande.
LECTURE = ["core.view_site", "core.view_service", "referentiels.view_unite", "referentiels.view_article"]
SAISIE = ["achats.view_demandeachat", "achats.add_demandeachat", "achats.change_demandeachat"]

ROLES = {
    "Achats - Demandeur": LECTURE + SAISIE,
    "Achats - Directeur technique": LECTURE + [
        "achats.view_demandeachat", "achats.voir_toutes_demandeachat",
        "achats.valider_direction_technique_demandeachat",
    ],
    "Achats - Responsable achats": LECTURE + SAISIE + [
        "achats.voir_toutes_demandeachat", "achats.valider_achats_demandeachat",
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
