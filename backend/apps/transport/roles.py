"""Rôles par défaut du module Transport. Ils restent modifiables dans l'administration."""

LECTURE = ["core.view_site", "referentiels.view_tiers", "technique.view_materiel", "transport.view_ordretransport"]

ROLES = {
    "Transport - Consultation": LECTURE,
    "Transport - Agent": LECTURE + ["transport.add_ordretransport", "transport.change_ordretransport"],
}


def creer_roles(sender, **kwargs):
    from django.contrib.auth.models import Group, Permission
    from django.db.models import Q

    for nom, droits in ROLES.items():
        groupe, cree = Group.objects.get_or_create(name=nom)
        if cree:  # on ne touche pas à un rôle déjà ajusté par l'administrateur
            filtre = Q()
            for droit in droits:
                app, code = droit.split(".")
                filtre |= Q(content_type__app_label=app, codename=code)
            groupe.permissions.set(Permission.objects.filter(filtre))
