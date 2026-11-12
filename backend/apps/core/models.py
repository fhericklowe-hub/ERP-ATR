import uuid
from pathlib import Path

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


class Societe(models.Model):
    """Coordonnées de l'entreprise, imprimées sur les documents. Une seule fiche."""

    nom = models.CharField(max_length=150)
    forme_capital = models.CharField("forme et capital", max_length=150, blank=True)
    adresse = models.CharField("siège social", max_length=255, blank=True)
    rccm = models.CharField("RCCM", max_length=60, blank=True)
    compte_contribuable = models.CharField("n° compte contribuable", max_length=30, blank=True)
    regime_imposition = models.CharField("régime d'imposition", max_length=60, blank=True)
    centre_impots = models.CharField("centre des impôts", max_length=60, blank=True)
    telephone = models.CharField("téléphone", max_length=80, blank=True)
    email = models.EmailField(blank=True)
    banque = models.CharField("coordonnées bancaires", max_length=120, blank=True)
    logo = models.ImageField(upload_to="societe/", blank=True)
    devise = models.CharField(max_length=5, default="XOF")
    taux_tva = models.DecimalField("taux de TVA par défaut (%)", max_digits=5, decimal_places=2, default=18)
    seuil_validation_dg = models.DecimalField(
        "seuil de validation par la direction générale", max_digits=14, decimal_places=0, default=1000000,
        help_text="Au-dessus de ce montant, une demande d'achat liée au budget est aussi validée par la direction générale.",
    )

    class Meta:
        verbose_name = "société"

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @property
    def chemin_logo(self) -> str:
        """Logo chargé dans l'administration, sinon celui fourni avec l'application."""
        if self.logo:
            return self.logo.path
        return str(Path(__file__).parent / "static" / "core" / "logo.png")

    @classmethod
    def courante(cls):
        return cls.objects.first() or cls(nom="Société à renseigner")


def chemin_signature(instance, nom_fichier):
    """Nom de fichier imprévisible : une signature ne doit pas se retrouver en devinant son adresse."""
    return f"signatures/{uuid.uuid4().hex}{Path(nom_fichier).suffix.lower()}"


class Utilisateur(AbstractUser):
    """Compte utilisateur. Les rôles sont les groupes Django, qui portent les droits."""

    site = models.ForeignKey(Site, null=True, blank=True, on_delete=models.PROTECT, related_name="utilisateurs")
    service = models.ForeignKey(Service, null=True, blank=True, on_delete=models.PROTECT, related_name="utilisateurs")
    telephone = models.CharField("téléphone", max_length=30, blank=True)
    fonction = models.CharField(max_length=100, blank=True)
    signature = models.ImageField(
        upload_to=chemin_signature, blank=True,
        help_text="Image de la signature (fond blanc ou transparent). Elle s'imprime automatiquement sur les "
                  "documents que cette personne a validés dans l'application.",
    )

    class Meta:
        verbose_name = "utilisateur"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return self.get_full_name() or self.username
