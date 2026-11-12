"""Bon de réception : constate ce qui a été livré sur un bon de commande transmis au fournisseur.
Une commande peut être reçue en plusieurs fois ; seules les réceptions validées comptent."""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone

from apps.core.models import Compteur, Horodate

from .commande import BonCommande, EvenementCommande, LigneBonCommande, arrondi


class BonReception(Horodate):
    class Statut(models.TextChoices):
        BROUILLON = "BROUILLON", "Brouillon"
        VALIDE = "VALIDE", "Validé"
        ANNULE = "ANNULE", "Annulé"

    numero = models.CharField("n° BR", max_length=20, unique=True, editable=False)
    ancien_numero = models.CharField("n° dans l'ancien logiciel", max_length=30, blank=True)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.BROUILLON, editable=False)
    date = models.DateField("date de réception", default=timezone.localdate)
    commande = models.ForeignKey(BonCommande, on_delete=models.PROTECT, related_name="receptions",
                                 verbose_name="bon de commande")
    numero_livraison = models.CharField("n° de livraison fournisseur", max_length=50, blank=True)
    receptionnaire = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bons_reception",
                                       verbose_name="réceptionnaire")
    observations = models.TextField(blank=True)
    valide_le = models.DateTimeField("validé le", null=True, blank=True, editable=False)
    annule_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, editable=False,
                                   on_delete=models.PROTECT, related_name="+")
    annule_le = models.DateTimeField("annulé le", null=True, blank=True, editable=False)
    motif_annulation = models.TextField("motif de l'annulation", blank=True, editable=False)

    class Meta:
        verbose_name = "bon de réception"
        verbose_name_plural = "bons de réception"
        ordering = ["-cree_le"]
        permissions = [("annuler_bonreception", "Peut annuler un bon de réception validé")]

    def __str__(self):
        return self.numero

    def save(self, *args, **kwargs):
        if not self.numero:
            with transaction.atomic():
                annee = self.date.year
                self.numero = f"BR-{annee}-{Compteur.suivant(f'BR-{annee}'):04d}"
                return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)

    @property
    def modifiable(self) -> bool:
        return self.statut == self.Statut.BROUILLON

    @property
    def total_ht(self) -> Decimal:
        """Valeur des quantités reçues, aux prix nets du bon de commande."""
        return sum((l.montant_ht for l in self.lignes.all()), Decimal(0))

    def peut_preparer(self, utilisateur) -> bool:
        return self.receptionnaire_id == utilisateur.id or utilisateur.has_perm("achats.annuler_bonreception")

    def peut_annuler(self, utilisateur) -> bool:
        return self.statut != self.Statut.ANNULE and (
            utilisateur.has_perm("achats.annuler_bonreception")
            or (self.modifiable and self.receptionnaire_id == utilisateur.id)
        )

    @transaction.atomic
    def valider(self, utilisateur):
        """Enregistre la réception : les quantités deviennent définitives et comptent sur la commande."""
        if not self.modifiable:
            raise ValidationError("Ce bon de réception n'est plus un brouillon.")
        if not self.peut_preparer(utilisateur):
            raise PermissionDenied("Seul le réceptionnaire ou le responsable achats peut valider ce bon de réception.")
        commande = BonCommande.objects.select_for_update().get(pk=self.commande_id)
        if commande.statut != BonCommande.Statut.TRANSMIS:
            raise ValidationError("La réception se fait sur un bon de commande transmis au fournisseur.")
        lignes = list(self.lignes.select_related("ligne_commande"))
        if not lignes:
            raise ValidationError("Indiquez au moins une quantité reçue.")
        deja = commande.quantites_recues()
        for l in lignes:
            lc = l.ligne_commande
            reste = lc.quantite - deja.get(lc.id, Decimal(0))
            if l.quantite_recue > reste:
                raise ValidationError(
                    f"« {lc.designation} » : {l.quantite_recue.normalize():f} reçu pour {reste.normalize():f} restant à recevoir."
                )
        self.statut = self.Statut.VALIDE
        self.valide_le = timezone.now()
        self.save()
        commande.evenements.create(auteur=utilisateur, action=EvenementCommande.Action.RECEPTION, statut=commande.statut,
                                   commentaire=f"{self.numero} ({commande.get_etat_reception_display()})")

    @transaction.atomic
    def annuler(self, utilisateur, commentaire):
        if not self.peut_annuler(utilisateur):
            raise PermissionDenied("Seul le responsable achats peut annuler un bon de réception validé.")
        if not commentaire.strip():
            raise ValidationError("Indiquez le motif de l'annulation.")
        etait_valide = self.statut == self.Statut.VALIDE
        self.statut = self.Statut.ANNULE
        self.annule_par, self.annule_le, self.motif_annulation = utilisateur, timezone.now(), commentaire.strip()
        self.save()
        if etait_valide:
            self.commande.evenements.create(
                auteur=utilisateur, action=EvenementCommande.Action.RECEPTION_ANNULEE, statut=self.commande.statut,
                commentaire=f"{self.numero} : {commentaire.strip()}",
            )


class LigneBonReception(models.Model):
    bon = models.ForeignKey(BonReception, on_delete=models.CASCADE, related_name="lignes")
    ligne_commande = models.ForeignKey(LigneBonCommande, on_delete=models.PROTECT, related_name="receptions")
    quantite_recue = models.DecimalField("quantité reçue", max_digits=12, decimal_places=2)
    quantite_stock = models.DecimalField("quantité à mettre en stock", max_digits=12, decimal_places=2, default=0)
    # Pour un matériel (engin, véhicule) : sa fiche sera créée dans le parc par le module Technique.
    numero_materiel = models.CharField("n° matériel", max_length=30, blank=True)
    numero_serie = models.CharField("n° de série", max_length=60, blank=True)
    immatriculation = models.CharField("immatriculation / identité", max_length=30, blank=True)
    observations = models.CharField("observations (conformité, réserves)", max_length=255, blank=True)

    class Meta:
        verbose_name = "ligne de bon de réception"
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(name="ligne_br_quantite_positive", condition=models.Q(quantite_recue__gt=0)),
            models.CheckConstraint(
                name="ligne_br_stock_valide",
                condition=models.Q(quantite_stock__gte=0, quantite_stock__lte=models.F("quantite_recue")),
            ),
            models.UniqueConstraint(fields=["bon", "ligne_commande"], name="ligne_br_unique_par_ligne_commande"),
        ]

    @property
    def montant_ht(self) -> Decimal:
        return arrondi(self.quantite_recue * self.ligne_commande.prix_net, self.ligne_commande.bon.devise)


def quantites_recues(commande) -> dict:
    """Quantité déjà reçue par ligne de commande, d'après les réceptions validées."""
    cumul = (LigneBonReception.objects.filter(bon__commande=commande, bon__statut=BonReception.Statut.VALIDE)
             .values("ligne_commande").annotate(total=Sum("quantite_recue")))
    return {c["ligne_commande"]: c["total"] for c in cumul}
