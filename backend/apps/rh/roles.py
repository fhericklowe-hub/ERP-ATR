"""Rôles par défaut des ressources humaines. Ils restent modifiables dans l'administration.
Les dossiers du personnel sont confidentiels : aucun autre rôle n'y a accès."""

LECTURE = ["core.view_site", "core.view_service", "core.view_utilisateur", "rh.view_salarie", "rh.view_contrat",
           "rh.view_piecesalarie"]
SAISIE = ["rh.add_salarie", "rh.change_salarie", "rh.add_contrat", "rh.change_contrat", "rh.delete_contrat",
          "rh.add_piecesalarie", "rh.change_piecesalarie", "rh.delete_piecesalarie", "rh.gerer_sortie_salarie"]

ABSENCES_VOIR = ["rh.view_demandeabsence"]
ABSENCES = ABSENCES_VOIR + ["rh.add_demandeabsence"]

ROLES = {
    # Tout salarié qui a un compte : il demande ses congés et voit ses demandes et celles de son équipe.
    "RH - Salarié": ABSENCES,
    "RH - Consultation": LECTURE + ABSENCES_VOIR,
    "RH - Gestionnaire": LECTURE + SAISIE + ABSENCES + ["rh.approuver_demandeabsence"],
}
# Ajoutés par migration aux rôles créés avant les congés.
DROITS_ABSENCES = {"RH - Consultation": ABSENCES_VOIR, "RH - Gestionnaire": ABSENCES + ["rh.approuver_demandeabsence"]}


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
