"""Contrats suivis par les moyens généraux et échéances à ne pas manquer (assurances, visites, taxes...)."""
import calendar
from datetime import date, timedelta

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.core.models import Compteur, Horodate, Site
from apps.referentiels.models import Tiers

from .models import Bien


def ajouter_mois(jour: date, mois: int) -> date:
    """Même jour, `mois` mois plus tard ; le 31 janvier donne le dernier jour de février."""
    annees, m = divmod(jour.month - 1 + mois, 12)
    annee, m = jour.year + annees, m + 1
    return date(annee, m, min(jour.day, calendar.monthrange(annee, m)[1]))


class Contrat(Horodate):
    class Type(models.TextChoices):
        ASSURANCE = "ASSURANCE", "Assurance"
        BAIL = "BAIL", "Bail ou location"
        MAINTENANCE = "MAINTENANCE", "Maintenance et entretien"
        GARDIENNAGE = "GARDIENNAGE", "Gardiennage et sécurité"
        NETTOYAGE = "NETTOYAGE", "Nettoyage"
        ABONNEMENT = "ABONNEMENT", "Abonnement (eau, électricité, téléphone, internet)"
        AUTRE = "AUTRE", "Autre"

    class Periodicite(models.TextChoices):
        MENSUELLE = "M", "Par mois"
        TRIMESTRIELLE = "T", "Par trimestre"
        SEMESTRIELLE = "S", "Par semestre"
        ANNUELLE = "A", "Par an"
        UNIQUE = "U", "En une fois"

    class Statut(models.TextChoices):
        ACTIF = "ACTIF", "En cours"
        RESILIE = "RESILIE", "Résilié ou terminé"

    numero = models.CharField("n°", max_length=20, unique=True, editable=False)
    type = models.CharField(max_length=12, choices=Type.choices)
    objet = models.CharField(max_length=150)
    prestataire = models.ForeignKey(Tiers, on_delete=models.PROTECT, related_name="contrats_moyens",
                                    verbose_name="prestataire ou bailleur")
    reference = models.CharField("référence du contrat ou n° de police", max_length=60, blank=True)
    site = models.ForeignKey(Site, null=True, blank=True, on_delete=models.PROTECT, related_name="contrats")
    bien = models.ForeignKey(Bien, null=True, blank=True, on_delete=models.PROTECT, related_name="contrats",
                             verbose_name="bien concerné")
    date_debut = models.DateField("date de début")
    date_fin = models.DateField("date de fin", null=True, blank=True)
    tacite_reconduction = models.BooleanField("tacite reconduction", default=False)
    preavis_jours = models.PositiveSmallIntegerField("préavis de résiliation (jours)", default=0)
    montant = models.DecimalField(max_digits=14, decimal_places=0, null=True, blank=True)
    periodicite = models.CharField("périodicité du montant", max_length=1, choices=Periodicite.choices,
                                   default=Periodicite.ANNUELLE)
    statut = models.CharField(max_length=8, choices=Statut.choices, default=Statut.ACTIF)
    observations = models.TextField(blank=True)

    class Meta:
        verbose_name = "contrat"
        ordering = ["-date_debut", "-id"]

    def __str__(self):
        return f"{self.numero} · {self.objet}"

    def clean(self):
        if self.date_fin and self.date_debut and self.date_fin < self.date_debut:
            raise ValidationError({"date_fin": "La date de fin est avant la date de début."})

    @property
    def date_limite_preavis(self):
        """Dernier jour pour résilier ou renégocier avant la fin du contrat."""
        return self.date_fin - timedelta(days=self.preavis_jours) if self.date_fin else None

    @transaction.atomic
    def save(self, *args, **kwargs):
        if not self.numero:
            annee = (self.date_debut or timezone.localdate()).year
            self.numero = f"CTR-{annee}-{Compteur.suivant(f'CTR-{annee}'):04d}"
        super().save(*args, **kwargs)
        self._suivre_la_fin()

    def _suivre_la_fin(self):
        """Tient à jour l'échéance « fin de contrat », placée à la date limite du préavis."""
        ouverte = self.echeances.filter(type=Echeance.Type.FIN_CONTRAT, statut=Echeance.Statut.A_FAIRE)
        if self.statut != self.Statut.ACTIF or not self.date_fin:
            ouverte.update(statut=Echeance.Statut.ANNULEE)
            return
        suite = "à reconduire ou résilier" if self.tacite_reconduction else "à renouveler"
        champs = dict(libelle=f"Fin du contrat {self.numero} ({self.objet}) : {suite}"[:150],
                      date_echeance=self.date_limite_preavis, site=self.site, bien=self.bien)
        if not ouverte.update(**champs):
            Echeance.objects.create(contrat=self, type=Echeance.Type.FIN_CONTRAT, cree_par=self.modifie_par,
                                    modifie_par=self.modifie_par, **champs)


class Echeance(Horodate):
    class Type(models.TextChoices):
        ASSURANCE = "ASSURANCE", "Assurance"
        VISITE_TECHNIQUE = "VISITE", "Visite technique"
        VIGNETTE = "VIGNETTE", "Vignette, patente et taxes"
        CONTROLE = "CONTROLE", "Contrôle réglementaire (extincteurs, électricité...)"
        PAIEMENT = "PAIEMENT", "Loyer ou paiement"
        FIN_CONTRAT = "FIN_CONTRAT", "Fin de contrat"
        AUTRE = "AUTRE", "Autre"

    class Statut(models.TextChoices):
        A_FAIRE = "A_FAIRE", "À faire"
        FAITE = "FAITE", "Faite"
        ANNULEE = "ANNULEE", "Annulée"

    type = models.CharField(max_length=12, choices=Type.choices)
    libelle = models.CharField("libellé", max_length=150)
    date_echeance = models.DateField("date d'échéance")
    rappel_jours = models.PositiveSmallIntegerField("prévenir (jours avant)", default=30)
    recurrence_mois = models.PositiveSmallIntegerField(
        "revient tous les (mois)", default=0, help_text="0 : l'échéance ne revient pas. 12 : tous les ans.")
    site = models.ForeignKey(Site, null=True, blank=True, on_delete=models.PROTECT, related_name="echeances")
    bien = models.ForeignKey(Bien, null=True, blank=True, on_delete=models.PROTECT, related_name="echeances",
                             verbose_name="bien concerné")
    contrat = models.ForeignKey(Contrat, null=True, blank=True, on_delete=models.PROTECT, related_name="echeances")
    montant_prevu = models.DecimalField("montant prévu", max_digits=14, decimal_places=0, null=True, blank=True)
    statut = models.CharField(max_length=8, choices=Statut.choices, default=Statut.A_FAIRE, editable=False)
    faite_le = models.DateField("faite le", null=True, blank=True, editable=False)
    faite_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, editable=False,
                                  on_delete=models.SET_NULL, related_name="+")
    montant_reel = models.DecimalField("montant réel", max_digits=14, decimal_places=0, null=True, blank=True, editable=False)
    commentaire = models.TextField(blank=True)

    class Meta:
        verbose_name = "échéance"
        ordering = ["date_echeance", "id"]

    def __str__(self):
        return f"{self.libelle} ({self.date_echeance:%d/%m/%Y})"

    @property
    def situation(self) -> str:
        """RETARD, PROCHE (dans le délai de rappel), A_VENIR, ou le statut si l'échéance n'est plus à faire."""
        if self.statut != self.Statut.A_FAIRE:
            return self.statut
        jours = (self.date_echeance - timezone.localdate()).days
        return "RETARD" if jours < 0 else "PROCHE" if jours <= self.rappel_jours else "A_VENIR"

    def _exiger_droit(self, utilisateur):
        if not utilisateur.has_perm("moyens.change_echeance"):
            raise PermissionDenied("Seuls les moyens généraux traitent les échéances.")
        if self.statut != self.Statut.A_FAIRE:
            raise ValidationError("Cette échéance n'est plus à faire.")

    @transaction.atomic
    def faire(self, utilisateur, faite_le=None, montant=None, commentaire="", prochaine=None):
        """Marque l'échéance faite. Si elle revient, crée la suivante et la renvoie."""
        self._exiger_droit(utilisateur)
        self.statut, self.faite_par = self.Statut.FAITE, utilisateur
        self.faite_le = faite_le or timezone.localdate()
        self.montant_reel = montant
        if commentaire:
            self.commentaire = commentaire
        self.modifie_par = utilisateur
        self.save()
        if not prochaine and self.recurrence_mois:
            prochaine = ajouter_mois(self.date_echeance, self.recurrence_mois)
        if not prochaine:
            return None
        if prochaine <= self.date_echeance:
            raise ValidationError("La prochaine échéance doit être après celle-ci.")
        return Echeance.objects.create(
            type=self.type, libelle=self.libelle, date_echeance=prochaine, rappel_jours=self.rappel_jours,
            recurrence_mois=self.recurrence_mois, site=self.site, bien=self.bien, contrat=self.contrat,
            montant_prevu=montant if montant is not None else self.montant_prevu,
            cree_par=utilisateur, modifie_par=utilisateur)

    def annuler(self, utilisateur, commentaire=""):
        self._exiger_droit(utilisateur)
        if not commentaire.strip():
            raise ValidationError("Indiquez pourquoi l'échéance est annulée.")
        self.statut, self.commentaire, self.modifie_par = self.Statut.ANNULEE, commentaire, utilisateur
        self.save()
