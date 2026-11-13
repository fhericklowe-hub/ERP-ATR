"""Rôle de direction : la lecture du tableau de bord, sans droit d'écriture dans les modules."""

ROLES = {"Direction - Tableau de bord": ["core.voir_pilotage"]}


def creer_roles(sender, **kwargs):
    from django.contrib.auth.models import Group, Permission

    for nom, droits in ROLES.items():
        groupe, cree = Group.objects.get_or_create(name=nom)
        if cree:  # on ne touche pas à un rôle déjà ajusté par l'administrateur
            groupe.permissions.set(Permission.objects.filter(content_type__app_label="core", codename__in=[d.split(".")[1] for d in droits]))
