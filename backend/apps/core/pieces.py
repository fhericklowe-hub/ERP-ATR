"""Pièces jointes : un fichier (devis, facture, contrat signé, photo...) attaché à n'importe quel document de l'ERP.

Chaque module déclare ses documents avec `declarer()`. Les droits suivent ceux du document : qui le voit peut
ouvrir ses pièces, qui peut le modifier peut en ajouter."""
import uuid
from pathlib import Path

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt", ".msg", ".eml"}
TAILLE_MAX = 10 * 1024 * 1024
# Seuls ces types s'affichent dans le navigateur ; les autres sont proposés en téléchargement.
AFFICHABLES = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}

_vues = {}


def declarer(vue):
    """Enregistre la vue d'API d'un document : son `get_queryset` dit quels objets un utilisateur peut voir."""
    _vues[vue.queryset.model._meta.label_lower] = vue


def modeles_declares():
    return sorted(_vues)


def objet_visible(request, modele: str, objet_id):
    """Le document `modele` n° `objet_id` si l'utilisateur a le droit de le voir, sinon None."""
    classe = _vues.get(modele)
    if not classe:
        return None
    meta = classe.queryset.model._meta
    if not request.user.has_perm(f"{meta.app_label}.view_{meta.model_name}"):
        return None
    vue = classe()
    vue.request, vue.action, vue.kwargs, vue.format_kwarg = request, "retrieve", {}, None
    try:
        return vue.get_queryset().filter(pk=objet_id).first()
    except (TypeError, ValueError):
        return None


def peut_modifier(utilisateur, objet) -> bool:
    meta = objet._meta
    return utilisateur.has_perm(f"{meta.app_label}.change_{meta.model_name}")


def chemin_piece(instance, nom_fichier):
    """Nom de fichier imprévisible : une pièce ne s'ouvre que par l'API, qui contrôle les droits."""
    return f"pieces/{uuid.uuid4().hex}{Path(nom_fichier).suffix.lower()}"


class PieceJointe(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT, related_name="+")
    object_id = models.PositiveBigIntegerField()
    objet = GenericForeignKey("content_type", "object_id")
    fichier = models.FileField(upload_to=chemin_piece, max_length=120)
    nom = models.CharField("nom du fichier", max_length=255)
    libelle = models.CharField("libellé", max_length=120, blank=True, help_text="Exemple : devis du fournisseur retenu")
    taille = models.PositiveIntegerField("taille (octets)", default=0)
    ajoute_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+",
                                   verbose_name="ajoutée par")
    ajoute_le = models.DateTimeField("ajoutée le", auto_now_add=True)

    class Meta:
        verbose_name = "pièce jointe"
        verbose_name_plural = "pièces jointes"
        ordering = ["ajoute_le", "id"]
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def __str__(self):
        return self.libelle or self.nom

    @property
    def extension(self):
        return Path(self.nom).suffix.lower()
