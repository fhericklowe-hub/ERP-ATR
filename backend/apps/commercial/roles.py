"""Rôles par défaut du module Commercial. Ils restent modifiables dans l'administration."""

LECTURE = ["core.view_site", "core.view_utilisateur", "referentiels.view_tiers", "technique.view_materiel",
           "commercial.view_devis", "commercial.view_opportunite"]
SAISIE = ["commercial.add_devis", "commercial.change_devis", "referentiels.add_tiers", "referentiels.change_tiers",
          "commercial.add_opportunite", "commercial.change_opportunite"]
# Fiche GO / NO GO : la finance et le DG n'ont besoin que de lire la fiche et de se prononcer.
FICHE = ["core.view_site", "core.view_utilisateur", "referentiels.view_tiers", "commercial.view_opportunite", "commercial.view_devis"]

ROLES = {
    "Commercial - Consultation": LECTURE,
    "Commercial - Commercial": LECTURE + SAISIE,
    "Commercial - Responsable": LECTURE + SAISIE + ["commercial.gerer_devis", "commercial.valider_responsable_opportunite"],
    "Commercial - Validation finance": FICHE + ["commercial.valider_finance_opportunite"],
    "Commercial - Validation DG": FICHE + ["commercial.valider_dg_opportunite"],
}
# Rôles qui existaient avant les fiches GO / NO GO : ils reçoivent ces droits par la migration.
DROITS_OPPORTUNITE = {
    "Commercial - Consultation": ["commercial.view_opportunite"],
    "Commercial - Commercial": ["commercial.view_opportunite", "commercial.add_opportunite", "commercial.change_opportunite"],
    "Commercial - Responsable": ["commercial.view_opportunite", "commercial.add_opportunite", "commercial.change_opportunite",
                                 "commercial.valider_responsable_opportunite"],
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
