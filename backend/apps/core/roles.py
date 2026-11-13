"""Rôle de direction : la lecture du tableau de bord, sans droit d'écriture dans les modules.
Rôle d'administration : créer les comptes et attribuer les rôles, sans droit dans les modules non plus."""

ROLE_COMPTES = "Administration - Comptes"
ROLES = {"Direction - Tableau de bord": ["core.voir_pilotage"],
         ROLE_COMPTES: ["core.gerer_comptes", "core.view_utilisateur", "core.view_site", "core.view_service"]}


def creer_roles(sender, **kwargs):
    from django.contrib.auth.models import Group, Permission

    for nom, droits in ROLES.items():
        groupe, cree = Group.objects.get_or_create(name=nom)
        if cree:  # on ne touche pas à un rôle déjà ajusté par l'administrateur
            groupe.permissions.set(Permission.objects.filter(content_type__app_label="core", codename__in=[d.split(".")[1] for d in droits]))
