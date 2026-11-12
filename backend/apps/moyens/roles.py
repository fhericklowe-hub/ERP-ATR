"""Rôles par défaut des Moyens généraux. Ils restent modifiables dans l'administration."""

LECTURE = ["core.view_site", "core.view_service", "moyens.view_bien"]
DEMANDE = ["moyens.view_demandeintervention", "moyens.add_demandeintervention", "moyens.change_demandeintervention"]

CONTRATS = ["moyens.view_contrat", "moyens.add_contrat", "moyens.change_contrat",
            "moyens.view_echeance", "moyens.add_echeance", "moyens.change_echeance"]

ROLES = {
    # Tout salarié qui peut signaler une panne ou demander une intervention.
    "Moyens généraux - Demandeur": LECTURE + DEMANDE,
    "Moyens généraux - Gestionnaire": LECTURE + DEMANDE + [
        "moyens.add_bien", "moyens.change_bien", "moyens.voir_toutes_demandeintervention",
        "moyens.traiter_demandeintervention", "referentiels.view_tiers", "core.view_utilisateur",
    ] + CONTRATS,
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
