"""Rôles par défaut du module Achats. Ils restent modifiables dans l'administration."""

# Listes nécessaires pour remplir une demande.
LECTURE = ["core.view_site", "core.view_service", "referentiels.view_unite", "referentiels.view_article"]
COMMANDE = [
    "achats.view_boncommande", "achats.add_boncommande", "achats.change_boncommande",
    "referentiels.view_tiers", "referentiels.add_tiers", "referentiels.change_tiers",
]
RECEPTION = [
    "achats.view_boncommande", "achats.view_bonreception", "achats.add_bonreception", "achats.change_bonreception",
    "referentiels.view_tiers",
]
# Demandes liées au budget
BUDGET_LECTURE = ["referentiels.view_projet", "referentiels.view_comptecharge", "achats.view_lignebudgetaire",
                  "achats.view_demandebudget"]
BUDGET_SAISIE = BUDGET_LECTURE + ["achats.add_demandebudget", "achats.change_demandebudget"]
BUDGET_TOUT_VOIR = BUDGET_LECTURE + ["achats.voir_toutes_demandebudget", "referentiels.view_tiers",
                                     "achats.view_boncommande"]
BUDGET = {
    "Achats - Demandeur": BUDGET_SAISIE,
    "Achats - Directeur technique": BUDGET_SAISIE,
    "Achats - Acheteur": BUDGET_SAISIE + BUDGET_TOUT_VOIR + ["achats.traiter_demandebudget"],
    "Achats - Contrôleur de gestion": BUDGET_SAISIE + BUDGET_TOUT_VOIR + [
        "achats.valider_controle_demandebudget", "achats.add_lignebudgetaire", "achats.change_lignebudgetaire",
    ],
    "Achats - Responsable achats": BUDGET_SAISIE + BUDGET_TOUT_VOIR + [
        "achats.traiter_demandebudget", "achats.valider_achats_demandebudget",
    ],
    "Achats - Direction financière": BUDGET_SAISIE + BUDGET_TOUT_VOIR + ["achats.valider_finance_demandebudget"],
    "Achats - Direction générale": BUDGET_SAISIE + BUDGET_TOUT_VOIR + ["achats.valider_dg_demandebudget"],
}
SAISIE = ["achats.view_demandeachat", "achats.add_demandeachat", "achats.change_demandeachat"]

ROLES = {
    "Achats - Demandeur": LECTURE + SAISIE,
    "Achats - Directeur technique": LECTURE + [
        "achats.view_demandeachat", "achats.voir_toutes_demandeachat",
        "achats.valider_direction_technique_demandeachat",
    ],
    "Achats - Magasinier": LECTURE + RECEPTION,
    "Achats - Acheteur": LECTURE + SAISIE + COMMANDE + RECEPTION + ["achats.voir_toutes_demandeachat", "achats.view_acheteur"],
    "Achats - Contrôleur de gestion": LECTURE + [
        "achats.view_demandeachat", "achats.voir_toutes_demandeachat",
        "achats.view_boncommande", "achats.valider_controle_boncommande", "achats.view_bonreception",
    ],
    "Achats - Responsable achats": LECTURE + SAISIE + COMMANDE + RECEPTION + [
        "achats.annuler_bonreception",
        "achats.valider_responsable_boncommande",
        "achats.voir_toutes_demandeachat", "achats.valider_achats_demandeachat",
        "achats.view_acheteur", "achats.change_acheteur",
    ],
}
ROLES["Achats - Direction financière"] = LECTURE
ROLES["Achats - Direction générale"] = LECTURE
for _role, _droits in BUDGET.items():
    ROLES[_role] = ROLES.get(_role, []) + _droits


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


# Droits du bon de réception à donner aux rôles créés avant lui (voir la migration 0005).
DROITS_RECEPTION = {
    "Achats - Acheteur": RECEPTION,
    "Achats - Contrôleur de gestion": ["achats.view_bonreception"],
    "Achats - Responsable achats": RECEPTION + ["achats.annuler_bonreception"],
}


def completer_roles(apps, droits_par_role, applications=("achats",)):
    """Pour une migration : ajoute des droits aux rôles créés avant une nouvelle fonction.
    Sur une base neuve il n'y a rien à faire, les rôles sont créés complets après les migrations."""
    from django.contrib.auth.management import create_permissions
    from django.db.models import Q

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    if not Group.objects.filter(name__in=droits_par_role).exists():
        return
    for nom in applications:
        config = apps.get_app_config(nom)
        config.models_module = True  # nécessaire pour créer les droits des nouveaux modèles dès maintenant
        create_permissions(config, apps=apps, verbosity=0)
        config.models_module = None
    for nom, droits in droits_par_role.items():
        groupe = Group.objects.filter(name=nom).first()
        if not groupe:
            continue
        filtre = Q()
        for droit in droits:
            app, code = droit.split(".")
            filtre |= Q(content_type__app_label=app, codename=code)
        groupe.permissions.add(*Permission.objects.filter(filtre))
