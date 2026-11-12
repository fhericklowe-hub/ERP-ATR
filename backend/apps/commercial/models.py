"""Commercial : le devis de location (matériel, espace de stockage, prestation), qui devient la commande du client
une fois accepté. Le document imprimé reprend le modèle actuel de l'entreprise."""
import datetime
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models, transaction
from django.utils import timezone

from apps.achats.choix import Activite
from apps.achats.commande import BonCommande
from apps.core.devises import arrondi
from apps.core.lettres import montant_en_lettres
from apps.core.models import Compteur, Horodate, Site
from apps.referentiels.models import Tiers

CENT = Decimal(100)


class ReglageCommercial(models.Model):
    """Une seule ligne : ce qui s'imprime sur tous les devis."""

    conditions_generales = models.FileField(
        "conditions générales de location (PDF)", upload_to="commercial/", blank=True,
        validators=[FileExtensionValidator(["pdf"])], help_text="Ce PDF est ajouté à la suite de chaque devis.")
    extrait_conditions = models.TextField(
        "extrait des conditions, en pied de devis", blank=True,
        help_text="Court texte imprimé en bas de la première page (« Extrait CGV location de matériel : ... »).")
    validite_jours = models.PositiveSmallIntegerField("validité d'un devis (jours)", default=30)

    class Meta:
        verbose_name = "réglages du commercial"
        verbose_name_plural = "réglages du commercial"

    def __str__(self):
        return "Réglages du commercial"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def courant(cls):
        return cls.objects.filter(pk=1).first() or cls()


class Devis(Horodate):
    class Statut(models.TextChoices):
        BROUILLON = "BROUILLON", "Brouillon"
        ENVOYE = "ENVOYE", "Envoyé au client"
        ACCEPTE = "ACCEPTE", "Accepté (commande client)"
        REFUSE = "REFUSE", "Refusé par le client"
        ANNULE = "ANNULE", "Annulé"

    class Loyer(models.TextChoices):
        JOUR = "JOUR", "Journalier"
        SEMAINE = "SEMAINE", "Hebdomadaire"
        MOIS = "MOIS", "Mensuel"
        FORFAIT = "FORFAIT", "Forfait"

    class Facturation(models.TextChoices):
        ECHU = "ECHU", "Échu terme"
        A_ECHOIR = "A_ECHOIR", "Terme à échoir"
        FIN = "FIN", "En fin de prestation"

    numero = models.CharField("n° de devis", max_length=20, unique=True, editable=False)
    statut = models.CharField(max_length=9, choices=Statut.choices, default=Statut.BROUILLON, editable=False)
    date = models.DateField(default=timezone.localdate)
    validite = models.DateField("valable jusqu'au", null=True, blank=True)
    client = models.ForeignKey(Tiers, on_delete=models.PROTECT, related_name="devis", limit_choices_to={"est_client": True})
    contact = models.CharField("interlocuteur chez le client", max_length=150, blank=True)
    libelle = models.CharField("libellé", max_length=200)
    activite = models.CharField("activité", max_length=12, choices=Activite.choices, blank=True)
    site = models.ForeignKey(Site, on_delete=models.PROTECT, related_name="devis", verbose_name="agence")
    commercial = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="devis",
                                   verbose_name="servi par")
    type_loyer = models.CharField("type de loyer", max_length=7, choices=Loyer.choices, default=Loyer.MOIS)
    date_debut = models.DateField("début prévu", null=True, blank=True)
    date_retour = models.DateTimeField("retour prévu", null=True, blank=True)
    lieu = models.CharField("lieu d'utilisation", max_length=200, blank=True)
    mode_facturation = models.CharField("mode de facturation", max_length=8, choices=Facturation.choices,
                                        default=Facturation.ECHU)
    echeance = models.CharField("échéance de paiement", max_length=100, blank=True, default="30 JOURS NETS")
    mode_reglement = models.CharField("mode de règlement", max_length=10, choices=BonCommande.Reglement.choices,
                                      default=BonCommande.Reglement.VIREMENT)
    exonere_tva = models.BooleanField("client exonéré de TVA", default=False)
    taux_tva = models.DecimalField("TVA (%)", max_digits=5, decimal_places=2, default=18)
    conditions = models.TextField("conditions particulières", blank=True)
    reference_client = models.CharField("n° de bon de commande du client", max_length=60, blank=True, editable=False)
    accepte_le = models.DateField("accepté le", null=True, blank=True, editable=False)
    motif = models.TextField("motif du refus ou de l'annulation", blank=True, editable=False)

    class Meta:
        verbose_name = "devis"
        verbose_name_plural = "devis"
        ordering = ["-cree_le"]
        permissions = [("gerer_devis", "Peut modifier et faire avancer les devis de tous les commerciaux")]

    def __str__(self):
        return self.numero

    @transaction.atomic
    def save(self, *args, **kwargs):
        if not self.numero:
            annee = timezone.localdate().year
            self.numero = f"DV-{annee}-{Compteur.suivant(f'DV-{annee}'):04d}"
        if not self.validite:
            self.validite = self.date + datetime.timedelta(days=ReglageCommercial.courant().validite_jours)
        super().save(*args, **kwargs)

    # ----- montants (en francs CFA, arrondis au franc)

    def totaux(self) -> dict:
        ht = sum((l.montant_ht for l in self.lignes.all()), Decimal(0))
        taux = Decimal(0) if self.exonere_tva else self.taux_tva
        tva = arrondi(ht * taux / CENT)
        return {"total_ht": ht, "taux_tva": taux, "total_tva": tva, "total_ttc": ht + tva,
                "en_lettres": montant_en_lettres(ht + tva)}

    # ----- qui peut quoi

    @property
    def expire(self) -> bool:
        return self.statut == self.Statut.ENVOYE and bool(self.validite) and self.validite < timezone.localdate()

    def peut_agir(self, u) -> bool:
        """Le commercial du devis, ou le responsable commercial."""
        return u.has_perm("commercial.gerer_devis") or (u.has_perm("commercial.change_devis") and self.commercial_id == u.id)

    def _exiger(self, utilisateur, *statuts):
        if not self.peut_agir(utilisateur):
            raise PermissionDenied("Ce devis est suivi par un autre commercial.")
        if self.statut not in statuts:
            raise ValidationError(f"Impossible sur un devis « {self.get_statut_display().lower()} ».")

    # ----- circuit

    def envoyer(self, utilisateur):
        S = self.Statut
        self._exiger(utilisateur, S.BROUILLON)
        if not self.lignes.exists():
            raise ValidationError("Ajoutez au moins une ligne au devis.")
        if self.validite < timezone.localdate():
            raise ValidationError("La date de validité est dépassée : corrigez-la avant l'envoi.")
        self.statut, self.modifie_par = S.ENVOYE, utilisateur
        self.save()

    def reprendre(self, utilisateur):
        """Le client demande une modification : le devis redevient un brouillon."""
        S = self.Statut
        self._exiger(utilisateur, S.ENVOYE, S.REFUSE)
        self.statut, self.motif, self.modifie_par = S.BROUILLON, "", utilisateur
        self.save()

    def accepter(self, utilisateur, reference_client="", accepte_le=None):
        S = self.Statut
        self._exiger(utilisateur, S.ENVOYE)
        accepte_le = accepte_le or timezone.localdate()
        if accepte_le > timezone.localdate() or accepte_le < self.date:
            raise ValidationError("La date d'acceptation doit être entre la date du devis et aujourd'hui.")
        self.statut, self.reference_client, self.accepte_le = S.ACCEPTE, reference_client.strip()[:60], accepte_le
        self.modifie_par = utilisateur
        self.save()

    def _fermer(self, utilisateur, statut, motif, *depuis):
        self._exiger(utilisateur, *depuis)
        if not motif.strip():
            raise ValidationError("Indiquez le motif.")
        self.statut, self.motif, self.modifie_par = statut, motif.strip(), utilisateur
        self.save()

    def refuser(self, utilisateur, motif):
        self._fermer(utilisateur, self.Statut.REFUSE, motif, self.Statut.ENVOYE)

    def annuler(self, utilisateur, motif):
        S = self.Statut
        if self.statut == S.ACCEPTE and not utilisateur.has_perm("commercial.gerer_devis"):
            raise PermissionDenied("Seul le responsable commercial annule une commande acceptée.")
        self._fermer(utilisateur, S.ANNULE, motif, S.BROUILLON, S.ENVOYE, S.ACCEPTE)


class LigneDevis(models.Model):
    devis = models.ForeignKey(Devis, on_delete=models.CASCADE, related_name="lignes")
    materiel = models.ForeignKey("technique.Materiel", null=True, blank=True, on_delete=models.PROTECT, related_name="+",
                                 verbose_name="matériel du parc")
    designation = models.CharField("référence / désignation", max_length=200)
    quantite = models.DecimalField("quantité", max_digits=10, decimal_places=2, default=1)
    prix_unitaire = models.DecimalField("prix unitaire HT", max_digits=14, decimal_places=2)
    remise = models.DecimalField("remise (%)", max_digits=5, decimal_places=2, default=0)
    duree = models.DecimalField("durée", max_digits=8, decimal_places=2, default=1,
                                help_text="Nombre de jours, de semaines ou de mois selon le type de loyer")

    class Meta:
        verbose_name = "ligne de devis"
        verbose_name_plural = "lignes de devis"
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(name="ligne_devis_quantite_positive", condition=models.Q(quantite__gt=0)),
            models.CheckConstraint(name="ligne_devis_prix_positif", condition=models.Q(prix_unitaire__gte=0)),
            models.CheckConstraint(name="ligne_devis_remise_valide", condition=models.Q(remise__gte=0, remise__lte=100)),
            models.CheckConstraint(name="ligne_devis_duree_positive", condition=models.Q(duree__gt=0)),
        ]

    @property
    def prix_net(self) -> Decimal:
        return arrondi(self.prix_unitaire * (CENT - self.remise) / CENT)

    @property
    def montant_ht(self) -> Decimal:
        return arrondi(self.quantite * self.prix_net * self.duree)
