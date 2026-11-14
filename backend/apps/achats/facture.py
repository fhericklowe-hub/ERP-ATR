"""Facture fournisseur : saisie du montant facturé et rapprochement avec le bon de commande et les réceptions validées.

Le paiement lui-même se fait en dehors de l'ERP (la comptabilité reste dans IE) : ici on contrôle la facture, on donne le
« bon à payer » (la facture correspond à ce qui a été reçu), puis on note le paiement."""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.core.models import Compteur, Horodate

from .commande import BonCommande


class FactureFournisseur(Horodate):
    class Statut(models.TextChoices):
        A_VERIFIER = "A_VERIFIER", "À vérifier"
        BON_A_PAYER = "BON_A_PAYER", "Bon à payer"
        PAYEE = "PAYEE", "Payée"
        ANNULEE = "ANNULEE", "Annulée"

    numero = models.CharField("n° interne", max_length=20, unique=True, editable=False)
    numero_facture = models.CharField("n° de la facture du fournisseur", max_length=50)
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.A_VERIFIER, editable=False)
    commande = models.ForeignKey(BonCommande, on_delete=models.PROTECT, related_name="factures", verbose_name="bon de commande")
    date_facture = models.DateField("date de la facture", default=timezone.localdate)
    date_echeance = models.DateField("échéance de paiement", null=True, blank=True)
    montant_ht = models.DecimalField("montant HT", max_digits=14, decimal_places=2)
    montant_ttc = models.DecimalField("montant TTC", max_digits=14, decimal_places=2)
    observations = models.TextField(blank=True)
    commentaire_ecart = models.TextField("justification de l'écart", blank=True, editable=False)
    bon_a_payer_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, editable=False,
                                        on_delete=models.PROTECT, related_name="+")
    bon_a_payer_le = models.DateTimeField(null=True, blank=True, editable=False)
    payee_le = models.DateField("payée le", null=True, blank=True, editable=False)
    reference_paiement = models.CharField("référence du paiement", max_length=100, blank=True, editable=False)
    motif_annulation = models.TextField("motif de l'annulation", blank=True, editable=False)

    class Meta:
        verbose_name = "facture fournisseur"
        verbose_name_plural = "factures fournisseurs"
        ordering = ["-date_facture", "-id"]
        permissions = [
            ("donner_bon_a_payer_facturefournisseur", "Peut donner le bon à payer d'une facture fournisseur"),
            ("payer_facturefournisseur", "Peut marquer une facture fournisseur comme payée"),
        ]
        constraints = [
            models.CheckConstraint(name="facture_montants_positifs", condition=models.Q(montant_ht__gt=0, montant_ttc__gte=models.F("montant_ht"))),
        ]

    def __str__(self):
        return f"{self.numero} ({self.numero_facture})"

    def save(self, *args, **kwargs):
        if not self.numero:
            annee = timezone.localdate().year
            with transaction.atomic():
                self.numero = f"FF-{annee}-{Compteur.suivant(f'FF-{annee}'):04d}"
        super().save(*args, **kwargs)

    @property
    def fournisseur(self):
        return self.commande.fournisseur

    @property
    def devise(self) -> str:
        return self.commande.devise

    @property
    def modifiable(self) -> bool:
        return self.statut == self.Statut.A_VERIFIER

    # ----- rapprochement

    def rapprochement(self) -> dict:
        """Compare le cumul facturé sur la commande à la valeur des réceptions validées (en HT)."""
        commande = self.commande
        recu = sum((r.total_ht for r in commande.receptions.filter(statut="VALIDE").prefetch_related("lignes__ligne_commande")), Decimal(0))
        autres = commande.factures.exclude(statut=self.Statut.ANNULEE).exclude(pk=self.pk).aggregate(t=models.Sum("montant_ht"))["t"] or Decimal(0)
        facture = Decimal(0) if self.statut == self.Statut.ANNULEE else self.montant_ht
        cumul = autres + facture
        tolerance = Decimal(1) if commande.devise == "XOF" else Decimal("0.01")
        ecart = cumul - recu
        return {
            "commande_ht": commande.totaux()["total_ht"], "recu_ht": recu, "autres_factures_ht": autres, "facture_ht": facture,
            "cumul_facture_ht": cumul, "ecart_ht": ecart, "conforme": abs(ecart) <= tolerance,
            "sens": "" if abs(ecart) <= tolerance else ("facture_superieure" if ecart > 0 else "facture_inferieure"),
        }

    # ----- circuit

    @transaction.atomic
    def donner_bon_a_payer(self, utilisateur, commentaire=""):
        if not utilisateur.has_perm("achats.donner_bon_a_payer_facturefournisseur"):
            raise PermissionDenied("Seul le responsable achats peut donner le bon à payer.")
        if self.statut != self.Statut.A_VERIFIER:
            raise ValidationError("Cette facture n'est plus à vérifier.")
        if not self.rapprochement()["conforme"] and not commentaire.strip():
            raise ValidationError("La facture ne correspond pas à ce qui a été reçu : justifiez l'écart pour donner le bon à payer.")
        self.statut = self.Statut.BON_A_PAYER
        self.commentaire_ecart = commentaire.strip()
        self.bon_a_payer_par, self.bon_a_payer_le = utilisateur, timezone.now()
        self.save()

    @transaction.atomic
    def payer(self, utilisateur, date_paiement=None, reference=""):
        if not utilisateur.has_perm("achats.payer_facturefournisseur"):
            raise PermissionDenied("Vous n'avez pas le droit de marquer une facture comme payée.")
        if self.statut != self.Statut.BON_A_PAYER:
            raise ValidationError("Le bon à payer doit d'abord être donné.")
        self.statut = self.Statut.PAYEE
        self.payee_le = date_paiement or timezone.localdate()
        self.reference_paiement = (reference or "").strip()
        self.save()

    @transaction.atomic
    def annuler(self, utilisateur, commentaire=""):
        if not (utilisateur.has_perm("achats.donner_bon_a_payer_facturefournisseur") or (self.modifiable and utilisateur.has_perm("achats.change_facturefournisseur"))):
            raise PermissionDenied("Vous ne pouvez pas annuler cette facture.")
        if self.statut in (self.Statut.PAYEE, self.Statut.ANNULEE):
            raise ValidationError("Une facture payée ou déjà annulée ne peut pas être annulée.")
        if not commentaire.strip():
            raise ValidationError("Indiquez le motif de l'annulation.")
        self.statut = self.Statut.ANNULEE
        self.motif_annulation = commentaire.strip()
        self.save()
