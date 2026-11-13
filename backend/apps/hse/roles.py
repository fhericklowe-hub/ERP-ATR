"""Rôles par défaut du module HSE. Ils restent modifiables dans l'administration."""

# « Modifier » sert à corriger sa propre déclaration avant l'analyse et à y joindre des photos.
BASE = ["core.view_site", "technique.view_materiel", "hse.view_evenement", "hse.add_evenement", "hse.change_evenement",
        "hse.view_actioncorrective"]

ROLES = {
    # Tout salarié qui a un compte : il déclare, et suit ses déclarations et les actions qui lui sont confiées.
    "HSE - Déclarant": BASE,
    "HSE - Responsable": BASE + ["core.view_utilisateur", "hse.traiter_evenement", "hse.add_actioncorrective",
                                 "hse.change_actioncorrective"],
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
