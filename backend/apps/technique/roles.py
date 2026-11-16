"""Rôles par défaut du module Technique. Ils restent modifiables dans l'administration."""

LECTURE = ["core.view_site", "core.view_service", "core.view_utilisateur", "referentiels.view_emplacement",
           "technique.view_materiel", "technique.view_ordrereparation", "technique.view_planentretien",
           "technique.view_pleincarburant"]
ATELIER = ["technique.add_ordrereparation", "technique.change_ordrereparation", "technique.add_pleincarburant"]

ROLES = {
    "Technique - Consultation": LECTURE,
    "Technique - Mécanicien": LECTURE + ATELIER,
    "Technique - Chef d'atelier": LECTURE + ATELIER + [
        "technique.add_materiel", "technique.change_materiel", "technique.piloter_ordrereparation",
        "technique.voir_couts_ordrereparation", "technique.view_reglageatelier", "technique.change_reglageatelier",
        "technique.add_reglageatelier", "technique.add_planentretien", "technique.change_planentretien", "technique.change_pleincarburant",
    ],
}

# Droits ajoutés avec l'entretien préventif, pour les rôles créés avant.
DROITS_ENTRETIEN = {
    "Technique - Consultation": ["technique.view_planentretien"],
    "Technique - Mécanicien": ["technique.view_planentretien"],
    "Technique - Chef d'atelier": ["technique.view_planentretien", "technique.add_planentretien",
                                   "technique.change_planentretien"],
}

# Droits ajoutés avec les pleins de carburant, pour les rôles créés avant (ceux qui roulent ou livrent saisissent aussi).
SAISIE_PLEIN = ["technique.view_pleincarburant", "technique.add_pleincarburant"]
DROITS_CARBURANT = {
    "Technique - Consultation": ["technique.view_pleincarburant"],
    "Technique - Mécanicien": SAISIE_PLEIN,
    "Technique - Chef d'atelier": SAISIE_PLEIN + ["technique.change_pleincarburant"],
    "Transport - Consultation": ["technique.view_pleincarburant"],
    "Transport - Agent": SAISIE_PLEIN,
    "Exploitation - Agent": SAISIE_PLEIN,
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
