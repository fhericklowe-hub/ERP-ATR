"""Rôles par défaut du module Achats. Ils restent modifiables dans l'administration."""

ROLES = {
    "Achats - Demandeur": ["view_demandeachat", "add_demandeachat", "change_demandeachat"],
    "Achats - Directeur technique": [
        "view_demandeachat", "voir_toutes_demandeachat", "valider_direction_technique_demandeachat",
    ],
    "Achats - Responsable achats": [
        "view_demandeachat", "add_demandeachat", "change_demandeachat",
        "voir_toutes_demandeachat", "valider_achats_demandeachat",
    ],
}


def creer_roles(sender, **kwargs):
    from django.contrib.auth.models import Group, Permission

    for nom, codes in ROLES.items():
        groupe, cree = Group.objects.get_or_create(name=nom)
        if cree:  # on ne touche pas à un rôle déjà ajusté par l'administrateur
            groupe.permissions.set(Permission.objects.filter(content_type__app_label="achats", codename__in=codes))
