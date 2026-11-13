"""Rôles par défaut du module HSE. Ils restent modifiables dans l'administration."""

# « Modifier » sert à corriger sa propre déclaration avant l'analyse et à y joindre des photos.
BASE = ["core.view_site", "technique.view_materiel", "hse.view_evenement", "hse.add_evenement", "hse.change_evenement",
        "hse.view_actioncorrective", "hse.view_visite"]

# Le visiteur choisit le responsable de chaque action qu'il décide : il lui faut la liste des comptes.
VISITES = ["hse.add_visite", "hse.change_visite", "hse.add_actioncorrective", "core.view_utilisateur"]
EPI = ["hse.view_dotationepi", "hse.add_dotationepi", "hse.change_dotationepi", "hse.delete_dotationepi"]

ROLES = {
    # Tout salarié qui a un compte : il déclare, et suit ses déclarations et les actions qui lui sont confiées.
    "HSE - Déclarant": BASE,
    # Encadrement qui mène des visites de sécurité sur le terrain.
    "HSE - Visiteur": BASE + VISITES,
    "HSE - Responsable": BASE + ["core.view_utilisateur", "hse.traiter_evenement", "hse.add_actioncorrective",
                                 "hse.change_actioncorrective"] + VISITES + EPI,
}
# Ajoutés par migration aux rôles créés avant les visites et les EPI.
DROITS_TERRAIN = {"HSE - Déclarant": ["hse.view_visite"], "HSE - Responsable": ["hse.view_visite"] + VISITES + EPI}


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
