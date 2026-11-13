"""Rappel quotidien par e-mail : chaque personne reçoit ce qui attend son action, selon ses droits.

Chaque module déclare ses rappels avec `rappels.declarer(fonction)` dans son `apps.py`. La fonction reçoit un
utilisateur et renvoie (titre, [lignes]) ou None s'il n'a rien à voir ou rien à faire."""
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

SOURCES = []
LIGNES_MAX = 30   # par rubrique ; au-delà on donne le compte


def declarer(fonction):
    if fonction not in SOURCES:
        SOURCES.append(fonction)


def composer(utilisateur) -> list:
    """Les rubriques du rappel de cette personne : [(titre, [lignes])]."""
    rubriques = []
    for source in SOURCES:
        rubrique = source(utilisateur)
        if rubrique and rubrique[1]:
            rubriques.append(rubrique)
    return rubriques


def accueil(utilisateur) -> list:
    """Les mêmes rubriques pour la page d'accueil, avec l'adresse de l'écran où les traiter."""
    rubriques = []
    for source in SOURCES:
        rubrique = source(utilisateur)
        if rubrique and rubrique[1]:
            titre, lignes = rubrique
            rubriques.append({"titre": titre, "lien": getattr(source, "lien", ""), "nombre": len(lignes), "lignes": lignes[:LIGNES_MAX]})
    return rubriques


def texte(utilisateur, rubriques) -> str:
    lignes = [f"Bonjour {utilisateur.first_name or utilisateur.username},", "",
              f"Voici ce qui attend votre attention dans l'ERP au {timezone.localdate():%d/%m/%Y}."]
    for titre, elements in rubriques:
        lignes += ["", f"{titre} ({len(elements)})"]
        lignes += [f"  - {e}" for e in elements[:LIGNES_MAX]]
        if len(elements) > LIGNES_MAX:
            lignes.append(f"  ... et {len(elements) - LIGNES_MAX} de plus.")
    if settings.ADRESSE_ERP:
        lignes += ["", f"Ouvrir l'ERP : {settings.ADRESSE_ERP}"]
    lignes += ["", "Ce message est envoyé automatiquement, il n'est pas nécessaire d'y répondre."]
    return "\n".join(lignes)


def destinataires():
    """Comptes actifs avec une adresse et au moins un rôle (un compte technique sans rôle ne reçoit rien)."""
    from .models import Utilisateur

    return Utilisateur.objects.filter(is_active=True, groups__isnull=False).exclude(email="").distinct()


def envoyer(simuler=False) -> list:
    """Envoie le rappel du jour. Renvoie [(utilisateur, nombre d'éléments)] pour ceux qui avaient quelque chose."""
    envoyes = []
    for utilisateur in destinataires():
        rubriques = composer(utilisateur)
        if not rubriques:
            continue
        nombre = sum(len(elements) for _, elements in rubriques)
        if not simuler:
            send_mail(f"ERP : {nombre} point(s) à traiter", texte(utilisateur, rubriques), None, [utilisateur.email])
        envoyes.append((utilisateur, nombre))
    return envoyes
