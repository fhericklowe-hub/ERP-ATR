from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import Horodate, Site


class Tiers(Horodate):
    """Client et/ou fournisseur. Un même tiers peut être les deux."""

    code = models.CharField(max_length=20, unique=True)
    raison_sociale = models.CharField(max_length=200)
    est_client = models.BooleanField("client", default=False)
    est_fournisseur = models.BooleanField("fournisseur", default=False)
    numero_contribuable = models.CharField("n° contribuable", max_length=50, blank=True)
    telephone = models.CharField("téléphone", max_length=30, blank=True)
    email = models.EmailField(blank=True)
    adresse = models.TextField(blank=True)
    ville = models.CharField(max_length=100, blank=True)
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "tiers"
        ordering = ["raison_sociale"]

    def __str__(self):
        return self.raison_sociale


class Contact(Horodate):
    tiers = models.ForeignKey(Tiers, on_delete=models.CASCADE, related_name="contacts")
    nom = models.CharField(max_length=150)
    fonction = models.CharField(max_length=100, blank=True)
    telephone = models.CharField("téléphone", max_length=30, blank=True)
    email = models.EmailField(blank=True)

    class Meta:
        ordering = ["nom"]

    def __str__(self):
        return f"{self.nom} ({self.tiers})"


class Emplacement(Horodate):
    """Lieu où peut se trouver un équipement ou un stock : un site de l'entreprise ou un site client."""

    class Type(models.TextChoices):
        SITE = "SITE", "Site de l'entreprise"
        CLIENT = "CLIENT", "Site client"

    type = models.CharField(max_length=10, choices=Type.choices)
    nom = models.CharField(max_length=150)
    site = models.ForeignKey(Site, null=True, blank=True, on_delete=models.PROTECT, related_name="emplacements")
    client = models.ForeignKey(
        Tiers, null=True, blank=True, on_delete=models.PROTECT, related_name="emplacements",
        limit_choices_to={"est_client": True},
    )
    adresse = models.TextField(blank=True)
    ville = models.CharField(max_length=100, blank=True)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["nom"]
        constraints = [
            models.CheckConstraint(
                name="emplacement_site_ou_client",
                condition=(
                    models.Q(type="SITE", site__isnull=False, client__isnull=True)
                    | models.Q(type="CLIENT", client__isnull=False, site__isnull=True)
                ),
            )
        ]

    def clean(self):
        if self.type == self.Type.SITE and (not self.site_id or self.client_id):
            raise ValidationError("Un emplacement de type site doit indiquer un site, sans client.")
        if self.type == self.Type.CLIENT and (not self.client_id or self.site_id):
            raise ValidationError("Un emplacement de type client doit indiquer un client, sans site.")

    def __str__(self):
        return self.nom


class Unite(models.Model):
    code = models.CharField(max_length=10, unique=True)
    nom = models.CharField(max_length=50)

    class Meta:
        verbose_name = "unité"
        ordering = ["code"]

    def __str__(self):
        return self.code


class FamilleArticle(models.Model):
    code = models.CharField(max_length=20, unique=True)
    nom = models.CharField(max_length=100)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="enfants")

    class Meta:
        verbose_name = "famille d'articles"
        verbose_name_plural = "familles d'articles"
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class Article(Horodate):
    """Tout ce qui s'achète ou se stocke : pièce, consommable, fourniture, service."""

    class Nature(models.TextChoices):
        PIECE = "PIECE", "Pièce détachée"
        CONSOMMABLE = "CONSO", "Consommable"
        FOURNITURE = "FOURN", "Fourniture"
        SERVICE = "SERVICE", "Service"
        IMMOBILISATION = "IMMO", "Immobilisation"

    code = models.CharField(max_length=30, unique=True)
    designation = models.CharField("désignation", max_length=200)
    nature = models.CharField(max_length=10, choices=Nature.choices, default=Nature.PIECE)
    famille = models.ForeignKey(FamilleArticle, null=True, blank=True, on_delete=models.PROTECT, related_name="articles")
    unite = models.ForeignKey(Unite, on_delete=models.PROTECT, related_name="articles", verbose_name="unité")
    gere_en_stock = models.BooleanField("géré en stock", default=True)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["designation"]

    def __str__(self):
        return f"{self.code} - {self.designation}"
