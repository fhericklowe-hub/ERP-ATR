"""Transport : l'ordre de transport, de la planification à la livraison. Un tracteur ou un camion, une remorque
éventuelle et un chauffeur pour un trajet entre deux lieux ; les compteurs et le carburant donnent les kilomètres
parcourus et la consommation."""
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.core.models import Compteur, Horodate, Site
from apps.referentiels.models import Tiers
from apps.technique.models import Materiel

TRACTEURS = ("TRACTEUR", "CAMION")


class OrdreTransport(Horodate):
    class Statut(models.TextChoices):
        PLANIFIE = "PLANIFIE", "Planifié"
        EN_COURS = "EN_COURS", "En route"
        LIVRE = "LIVRE", "Livré"
        ANNULE = "ANNULE", "Annulé"

    numero = models.CharField("n° d'ordre", max_length=20, unique=True, editable=False)
    statut = models.CharField(max_length=8, choices=Statut.choices, default=Statut.PLANIFIE, editable=False)
    client = models.ForeignKey(Tiers, on_delete=models.PROTECT, related_name="ordres_transport", limit_choices_to={"est_client": True})
    reference_client = models.CharField("référence du client (BL, booking, conteneur)", max_length=80, blank=True)
    site = models.ForeignKey(Site, on_delete=models.PROTECT, related_name="ordres_transport", verbose_name="agence")
    origine = models.CharField("lieu de chargement", max_length=200)
    destination = models.CharField("lieu de livraison", max_length=200)
    marchandise = models.CharField(max_length=200, blank=True)
    poids_tonnes = models.DecimalField("poids (tonnes)", max_digits=8, decimal_places=2, null=True, blank=True)
    nombre_colis = models.PositiveIntegerField("conteneurs ou colis", null=True, blank=True)
    date_prevue = models.DateField("départ prévu le")
    tracteur = models.ForeignKey(Materiel, on_delete=models.PROTECT, related_name="ordres_transport", verbose_name="tracteur ou camion")
    remorque = models.ForeignKey(Materiel, null=True, blank=True, on_delete=models.PROTECT, related_name="ordres_transport_remorque")
    chauffeur = models.CharField(max_length=120)
    prix_ht = models.DecimalField("prix du transport HT (XOF)", max_digits=14, decimal_places=2, null=True, blank=True)
    observations = models.TextField(blank=True)

    depart_le = models.DateTimeField("parti le", null=True, blank=True, editable=False)
    km_depart = models.PositiveIntegerField(null=True, blank=True, editable=False)
    arrivee_le = models.DateTimeField("livré le", null=True, blank=True, editable=False)
    km_arrivee = models.PositiveIntegerField(null=True, blank=True, editable=False)
    carburant_litres = models.DecimalField("carburant consommé (litres)", max_digits=8, decimal_places=1, null=True, blank=True,
                                           editable=False)
    reserves = models.TextField("réserves à la livraison", blank=True, editable=False)
    motif_annulation = models.TextField(blank=True, editable=False)

    class Meta:
        verbose_name = "ordre de transport"
        verbose_name_plural = "ordres de transport"
        ordering = ["-date_prevue", "-id"]

    def __str__(self):
        return self.numero

    @transaction.atomic
    def save(self, *args, **kwargs):
        if not self.numero:
            annee = timezone.localdate().year
            self.numero = f"OT-{annee}-{Compteur.suivant(f'OT-{annee}'):04d}"
        super().save(*args, **kwargs)

    @property
    def km_parcourus(self):
        return None if self.km_depart is None or self.km_arrivee is None else self.km_arrivee - self.km_depart

    @property
    def consommation_100km(self):
        km = self.km_parcourus
        if not km or self.carburant_litres is None:
            return None
        return (self.carburant_litres * 100 / km).quantize(Decimal("0.1"))

    def clean(self):
        if self.tracteur_id and self.tracteur.type not in TRACTEURS:
            raise ValidationError({"tracteur": "Il faut un tracteur routier ou un camion."})
        if self.remorque_id and self.remorque.type != "REMORQUE":
            raise ValidationError({"remorque": "Il faut une remorque ou une semi-remorque."})

    def _exiger(self, utilisateur, *statuts):
        if not utilisateur.has_perm("transport.change_ordretransport"):
            raise PermissionDenied("Seul le transport fait avancer les ordres.")
        if self.statut not in statuts:
            raise ValidationError(f"Impossible : cet ordre est « {self.get_statut_display().lower()} ».")

    @transaction.atomic
    def demarrer(self, utilisateur, moment=None, km=None):
        self._exiger(utilisateur, self.Statut.PLANIFIE)
        moment = moment or timezone.now()
        if moment > timezone.now():
            raise ValidationError("La date de départ ne peut pas être dans le futur.")
        if km is None:
            raise ValidationError("Relevez le compteur du tracteur au départ.")
        tracteur = Materiel.objects.select_for_update().get(pk=self.tracteur_id)
        if tracteur.etat in (Materiel.Etat.EN_PANNE, Materiel.Etat.EN_REPARATION, Materiel.Etat.REFORME):
            raise ValidationError(f"Le tracteur {tracteur.code} est « {tracteur.get_etat_display().lower()} ».")
        if tracteur.compteur_km is not None and km < tracteur.compteur_km:
            raise ValidationError(f"Compteur inférieur au dernier relevé du matériel ({tracteur.compteur_km} km).")
        for materiel, libelle in ((self.tracteur_id, "tracteur"), (self.remorque_id, "remorque")):
            if materiel and OrdreTransport.objects.filter(statut=self.Statut.EN_COURS).exclude(pk=self.pk).filter(
                    models.Q(tracteur_id=materiel) | models.Q(remorque_id=materiel)).exists():
                raise ValidationError(f"La {libelle} est déjà sur un autre ordre en route.")
        tracteur.compteur_km = km
        tracteur.modifie_par = utilisateur
        tracteur.save(update_fields=["compteur_km", "modifie_par", "modifie_le"])
        self.statut, self.depart_le, self.km_depart, self.modifie_par = self.Statut.EN_COURS, moment, km, utilisateur
        self.save()

    @transaction.atomic
    def livrer(self, utilisateur, moment=None, km=None, litres=None, reserves=""):
        self._exiger(utilisateur, self.Statut.EN_COURS)
        moment = moment or timezone.now()
        if moment > timezone.now() or moment < self.depart_le:
            raise ValidationError("La date de livraison doit être entre le départ et maintenant.")
        if km is None or km < self.km_depart:
            raise ValidationError("Le compteur à l'arrivée ne peut pas être inférieur à celui du départ.")
        tracteur = Materiel.objects.select_for_update().get(pk=self.tracteur_id)
        tracteur.compteur_km = max(tracteur.compteur_km or 0, km)
        tracteur.modifie_par = utilisateur
        tracteur.save(update_fields=["compteur_km", "modifie_par", "modifie_le"])
        self.statut, self.arrivee_le, self.km_arrivee = self.Statut.LIVRE, moment, km
        self.carburant_litres, self.reserves, self.modifie_par = litres, reserves.strip(), utilisateur
        self.save()

    def annuler(self, utilisateur, motif):
        self._exiger(utilisateur, self.Statut.PLANIFIE, self.Statut.EN_COURS)
        if not motif.strip():
            raise ValidationError("Indiquez le motif.")
        self.statut, self.motif_annulation, self.modifie_par = self.Statut.ANNULE, motif.strip(), utilisateur
        self.save()
