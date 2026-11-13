"""Journal des modifications : qui a créé, modifié ou supprimé quoi, et quand.

Seules les actions faites par un utilisateur connecté, dans une requête de l'application, sont tracées
(pas les commandes d'import en console ni les tâches de fond). Les valeurs des dossiers du personnel et
des mots de passe ne sont jamais écrites : on garde seulement le nom des champs modifiés."""
import contextvars
from datetime import date, datetime
from decimal import Decimal

from django.apps import apps
from django.db.models.signals import post_delete, post_save, pre_save

APPLICATIONS = {"achats", "commercial", "core", "exploitation", "hse", "moyens", "referentiels", "rh", "stock", "technique"}
IGNORES = {"core.trace", "core.compteur"}  # le journal lui-même, les compteurs de numérotation
CONFIDENTIELS = {"rh"}  # applications dont les valeurs ne sont pas écrites
CHAMPS_SECRETS = {"password"}
CHAMPS_BRUITS = {"last_login", "modifie_le", "modifie_par", "cree_le", "cree_par"}

contexte = contextvars.ContextVar("journal_contexte", default=None)


class MiddlewareJournal:
    """Ouvre le contexte de la requête et le referme : rien ne passe d'une requête à l'autre."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        jeton = contexte.set({"requete": request})
        try:
            return self.get_response(request)
        finally:
            contexte.reset(jeton)


def _suivi(modele):
    return modele._meta.app_label in APPLICATIONS and modele._meta.label_lower not in IGNORES and "evenement" not in modele._meta.model_name


def _simple(valeur):
    if valeur is None or isinstance(valeur, (bool, int, float, str)):
        return valeur
    if isinstance(valeur, (date, datetime)):
        return valeur.isoformat()
    if isinstance(valeur, Decimal):
        return str(valeur)
    return str(valeur)


def _valeurs(instance):
    return {c.attname: c.value_from_object(instance) for c in instance._meta.concrete_fields if c.name not in CHAMPS_BRUITS}


def _utilisateur():
    courant = contexte.get()
    # DRF dépose l'utilisateur authentifié (jeton JWT) sur la requête Django ; l'administration Django, sa session.
    utilisateur = getattr(courant["requete"], "user", None) if courant else None
    return utilisateur if utilisateur is not None and getattr(utilisateur, "pk", None) else None


def _avant_enregistrement(sender, instance, raw=False, **kwargs):
    if raw or not _suivi(sender) or contexte.get() is None:
        return
    anterieur = sender._default_manager.filter(pk=instance.pk).first() if instance.pk else None
    instance._journal_avant = _valeurs(anterieur) if anterieur else None


def _apres_enregistrement(sender, instance, created, raw=False, **kwargs):
    from .models import Trace

    if raw or not _suivi(sender) or not _utilisateur():
        return
    changements = {}
    if not created:
        avant = getattr(instance, "_journal_avant", None) or {}
        confidentiel = sender._meta.app_label in CONFIDENTIELS
        for champ, apres in _valeurs(instance).items():
            if champ in avant and avant[champ] != apres:
                secret = confidentiel or champ in CHAMPS_SECRETS
                changements[champ] = None if secret else [_simple(avant[champ]), _simple(apres)]
        if not changements:
            return
    Trace.objects.create(utilisateur=_utilisateur(), action=Trace.CREATION if created else Trace.MODIFICATION,
                         modele=sender._meta.label_lower, objet_id=instance.pk, objet_libelle=str(instance)[:200], changements=changements)


def _apres_suppression(sender, instance, **kwargs):
    from .models import Trace

    if not _suivi(sender) or not _utilisateur():
        return
    Trace.objects.create(utilisateur=_utilisateur(), action=Trace.SUPPRESSION, modele=sender._meta.label_lower,
                         objet_id=instance.pk, objet_libelle=str(instance)[:200], changements={})


def brancher():
    for modele in apps.get_models():
        if _suivi(modele):
            pre_save.connect(_avant_enregistrement, sender=modele, dispatch_uid=f"journal-avant-{modele._meta.label_lower}")
            post_save.connect(_apres_enregistrement, sender=modele, dispatch_uid=f"journal-apres-{modele._meta.label_lower}")
            post_delete.connect(_apres_suppression, sender=modele, dispatch_uid=f"journal-suppr-{modele._meta.label_lower}")
