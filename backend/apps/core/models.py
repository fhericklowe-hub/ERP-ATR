from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class Horodate(models.Model):
    """Base de tous les objets métier : qui a créé ou modifié, et quand."""

    cree_le = models.DateTimeField("créé le", auto_now_add=True)
    modifie_le = models.DateTimeField("modifié le", auto_now=True)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="créé par", null=True, blank=True,
        editable=False, on_delete=models.SET_NULL, related_name="+",
    )
    modifie_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="modifié par", null=True, blank=True,
        editable=False, on_delete=models.SET_NULL, related_name="+",
    )

    class Meta:
        abstract = True


class Site(Horodate):
    """Site de l'entreprise (siège, agence, dépôt)."""

    code = models.CharField(max_length=10, unique=True)
    nom = models.CharField(max_length=100)
    ville = models.CharField(max_length=100, blank=True)
    adresse = models.TextField(blank=True)
    est_siege = models.BooleanField("siège", default=False)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class Service(Horodate):
    """Service de l'entreprise (Achats, Technique, Commercial...)."""

    code = models.CharField(max_length=10, unique=True)
    nom = models.CharField(max_length=100)
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="services_diriges", help_text="Valide les demandes d'achat de son service.",
    )
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class Compteur(models.Model):
    """Dernier numéro attribué pour une série de documents (ex. DA-2026)."""

    cle = models.CharField(max_length=50, unique=True)
    valeur = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.cle} = {self.valeur}"

    @classmethod
    def suivant(cls, cle: str) -> int:
        """Renvoie le numéro suivant de la série. À appeler dans une transaction."""
        compteur, _ = cls.objects.select_for_update().get_or_create(cle=cle)
        compteur.valeur += 1
        compteur.save(update_fields=["valeur"])
        return compteur.valeur


class Utilisateur(AbstractUser):
    """Compte utilisateur. Les rôles sont les groupes Django, qui portent les droits."""

    site = models.ForeignKey(Site, null=True, blank=True, on_delete=models.PROTECT, related_name="utilisateurs")
    service = models.ForeignKey(Service, null=True, blank=True, on_delete=models.PROTECT, related_name="utilisateurs")
    telephone = models.CharField("téléphone", max_length=30, blank=True)
    fonction = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "utilisateur"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return self.get_full_name() or self.username
