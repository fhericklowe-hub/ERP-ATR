"""Moyens généraux : inventaire des biens de l'entreprise et demandes internes d'intervention."""
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.core.models import Compteur, Horodate, Service, Site
from apps.referentiels.models import Tiers


class Bien(Horodate):
    """Bien suivi par les moyens généraux. Les engins d'exploitation relèvent du module Technique."""

    class Categorie(models.TextChoices):
        BATIMENT = "BATIMENT", "Bâtiment ou local"
        VEHICULE = "VEHICULE", "Véhicule de service"
        MOBILIER = "MOBILIER", "Mobilier"
        INFORMATIQUE = "INFORMATIQUE", "Matériel informatique"
        TELEPHONIE = "TELEPHONIE", "Téléphonie"
        EQUIPEMENT = "EQUIPEMENT", "Équipement (climatisation, groupe électrogène...)"
        AUTRE = "AUTRE", "Autre"

    class Etat(models.TextChoices):
        EN_SERVICE = "EN_SERVICE", "En service"
        EN_PANNE = "EN_PANNE", "En panne"
        EN_REPARATION = "REPARATION", "En réparation"
        REFORME = "REFORME", "Réformé"

    numero = models.CharField("n° d'inventaire", max_length=20, unique=True, editable=False)
    categorie = models.CharField("catégorie", max_length=12, choices=Categorie.choices)
    designation = models.CharField("désignation", max_length=150)
    marque = models.CharField(max_length=60, blank=True)
    modele = models.CharField("modèle", max_length=60, blank=True)
    numero_serie = models.CharField("n° de série", max_length=60, blank=True)
    immatriculation = models.CharField(max_length=30, blank=True)
    site = models.ForeignKey(Site, on_delete=models.PROTECT, related_name="biens")
    emplacement = models.CharField("emplacement précis", max_length=100, blank=True, help_text="Bureau, étage, atelier...")
    service = models.ForeignKey(Service, null=True, blank=True, on_delete=models.PROTECT, related_name="biens",
                                verbose_name="service utilisateur")
    affecte_a = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name="biens_affectes", verbose_name="affecté à")
    date_acquisition = models.DateField("date d'acquisition", null=True, blank=True)
    valeur_acquisition = models.DecimalField("valeur d'acquisition", max_digits=14, decimal_places=0, null=True, blank=True)
    fournisseur = models.ForeignKey(Tiers, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    etat = models.CharField("état", max_length=10, choices=Etat.choices, default=Etat.EN_SERVICE)
    observations = models.TextField(blank=True)

    class Meta:
        verbose_name = "bien"
        ordering = ["numero"]

    def __str__(self):
        return f"{self.numero} · {self.designation}"

    def save(self, *args, **kwargs):
        if not self.numero:
            with transaction.atomic():
                self.numero = f"MG-{Compteur.suivant('MG-BIEN'):05d}"
                return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)


class DemandeIntervention(Horodate):
    class Categorie(models.TextChoices):
        ELECTRICITE = "ELECTRICITE", "Électricité"
        PLOMBERIE = "PLOMBERIE", "Plomberie"
        CLIMATISATION = "CLIMATISATION", "Climatisation"
        BATIMENT = "BATIMENT", "Bâtiment (menuiserie, serrurerie, peinture)"
        INFORMATIQUE = "INFORMATIQUE", "Informatique et téléphonie"
        VEHICULE = "VEHICULE", "Véhicule de service"
        MOBILIER = "MOBILIER", "Mobilier"
        NETTOYAGE = "NETTOYAGE", "Nettoyage et entretien"
        AUTRE = "AUTRE", "Autre"

    class Priorite(models.IntegerChoices):
        URGENTE = 1, "Urgente (sécurité ou activité bloquée)"
        NORMALE = 2, "Normale"
        BASSE = 3, "Peut attendre"

    class Statut(models.TextChoices):
        NOUVELLE = "NOUVELLE", "Nouvelle"
        PRISE_EN_CHARGE = "EN_COURS", "Prise en charge"
        REALISEE = "REALISEE", "Réalisée, à confirmer par le demandeur"
        CLOTUREE = "CLOTUREE", "Clôturée"
        REFUSEE = "REFUSEE", "Refusée"

    numero = models.CharField("n°", max_length=20, unique=True, editable=False)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.NOUVELLE, editable=False)
    demandeur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="demandes_intervention")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="demandes_intervention")
    site = models.ForeignKey(Site, on_delete=models.PROTECT, related_name="demandes_intervention")
    lieu = models.CharField("lieu précis", max_length=100, blank=True)
    bien = models.ForeignKey(Bien, null=True, blank=True, on_delete=models.PROTECT, related_name="interventions",
                             verbose_name="bien concerné")
    categorie = models.CharField("catégorie", max_length=13, choices=Categorie.choices)
    priorite = models.PositiveSmallIntegerField("priorité", choices=Priorite.choices, default=Priorite.NORMALE)
    objet = models.CharField(max_length=150)
    description = models.TextField(blank=True)

    # Prise en charge par les moyens généraux
    intervenant = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
                                    related_name="interventions", verbose_name="intervenant interne")
    prestataire = models.ForeignKey(Tiers, null=True, blank=True, on_delete=models.PROTECT, related_name="+",
                                    limit_choices_to={"est_fournisseur": True})
    date_prevue = models.DateField("date prévue", null=True, blank=True)
    prise_en_charge_le = models.DateTimeField(null=True, blank=True, editable=False)
    realisee_le = models.DateField("réalisée le", null=True, blank=True)
    compte_rendu = models.TextField("compte rendu", blank=True)
    cout = models.DecimalField("coût", max_digits=14, decimal_places=0, null=True, blank=True)
    cloturee_le = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "demande d'intervention"
        verbose_name_plural = "demandes d'intervention"
        ordering = ["-cree_le"]
        permissions = [
            ("voir_toutes_demandeintervention", "Peut voir toutes les demandes d'intervention"),
            ("traiter_demandeintervention", "Peut prendre en charge et traiter les demandes d'intervention"),
        ]

    def __str__(self):
        return self.numero

    def save(self, *args, **kwargs):
        if not self.numero:
            with transaction.atomic():
                annee = timezone.localdate().year
                self.numero = f"INT-{annee}-{Compteur.suivant(f'INT-{annee}'):04d}"
                return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)

    # ----- droits

    @property
    def modifiable(self) -> bool:
        return self.statut == self.Statut.NOUVELLE

    def peut_traiter(self, utilisateur) -> bool:
        return utilisateur.has_perm("moyens.traiter_demandeintervention")

    def _exiger_gestionnaire(self, utilisateur):
        if not self.peut_traiter(utilisateur):
            raise PermissionDenied("Seuls les moyens généraux peuvent traiter cette demande.")

    def _journal(self, utilisateur, action, commentaire=""):
        self.evenements.create(auteur=utilisateur, action=action, statut=self.statut, commentaire=commentaire)

    # ----- circuit

    @transaction.atomic
    def prendre_en_charge(self, utilisateur, intervenant=None, prestataire=None, date_prevue=None, commentaire=""):
        """Les moyens généraux désignent qui intervient (un collègue ou un prestataire) et quand."""
        self._exiger_gestionnaire(utilisateur)
        if self.statut not in (self.Statut.NOUVELLE, self.Statut.PRISE_EN_CHARGE):
            raise ValidationError("Cette demande n'est plus à prendre en charge.")
        if not intervenant and not prestataire:
            raise ValidationError("Désignez un intervenant interne ou un prestataire.")
        nouvelle = self.statut == self.Statut.NOUVELLE
        self.intervenant, self.prestataire, self.date_prevue = intervenant, prestataire, date_prevue
        self.statut = self.Statut.PRISE_EN_CHARGE
        if nouvelle:
            self.prise_en_charge_le = timezone.now()
        self.save()
        qui = " et ".join(str(x) for x in (intervenant, prestataire) if x)
        self._journal(utilisateur, Evenement.Action.PRISE_EN_CHARGE if nouvelle else Evenement.Action.REAFFECTATION,
                      f"{qui}. {commentaire}".strip() if commentaire else qui)
        if self.bien_id and self.bien.etat == Bien.Etat.EN_PANNE:
            Bien.objects.filter(pk=self.bien_id).update(etat=Bien.Etat.EN_REPARATION)

    @transaction.atomic
    def realiser(self, utilisateur, compte_rendu, cout=None, realisee_le=None):
        if not (self.peut_traiter(utilisateur) or utilisateur.id == self.intervenant_id):
            raise PermissionDenied("Seuls les moyens généraux ou l'intervenant peuvent déclarer l'intervention réalisée.")
        if self.statut != self.Statut.PRISE_EN_CHARGE:
            raise ValidationError("Seule une demande prise en charge peut être déclarée réalisée.")
        if not compte_rendu.strip():
            raise ValidationError("Décrivez ce qui a été fait.")
        self.compte_rendu, self.cout = compte_rendu.strip(), cout
        self.realisee_le = realisee_le or timezone.localdate()
        self.statut = self.Statut.REALISEE
        self.save()
        self._journal(utilisateur, Evenement.Action.REALISATION, self.compte_rendu)

    @transaction.atomic
    def cloturer(self, utilisateur, commentaire=""):
        """Le demandeur confirme que le problème est réglé ; les moyens généraux peuvent clôturer à sa place."""
        if not (utilisateur.id == self.demandeur_id or self.peut_traiter(utilisateur)):
            raise PermissionDenied("Seul le demandeur ou les moyens généraux peuvent clôturer la demande.")
        if self.statut != self.Statut.REALISEE:
            raise ValidationError("Seule une intervention réalisée peut être clôturée.")
        self.statut = self.Statut.CLOTUREE
        self.cloturee_le = timezone.now()
        self.save()
        self._journal(utilisateur, Evenement.Action.CLOTURE, commentaire)
        if self.bien_id and self.bien.etat in (Bien.Etat.EN_PANNE, Bien.Etat.EN_REPARATION):
            Bien.objects.filter(pk=self.bien_id).update(etat=Bien.Etat.EN_SERVICE)

    @transaction.atomic
    def rouvrir(self, utilisateur, commentaire):
        """Le problème n'est pas réglé : la demande repart en prise en charge."""
        if not (utilisateur.id == self.demandeur_id or self.peut_traiter(utilisateur)):
            raise PermissionDenied("Seul le demandeur ou les moyens généraux peuvent rouvrir la demande.")
        if self.statut not in (self.Statut.REALISEE, self.Statut.CLOTUREE):
            raise ValidationError("Seule une intervention réalisée ou clôturée peut être rouverte.")
        if not commentaire.strip():
            raise ValidationError("Indiquez ce qui ne va pas.")
        self.statut = self.Statut.PRISE_EN_CHARGE
        self.cloturee_le = None
        self.save()
        self._journal(utilisateur, Evenement.Action.REOUVERTURE, commentaire)

    @transaction.atomic
    def refuser(self, utilisateur, commentaire):
        self._exiger_gestionnaire(utilisateur)
        if self.statut not in (self.Statut.NOUVELLE, self.Statut.PRISE_EN_CHARGE):
            raise ValidationError("Cette demande ne peut plus être refusée.")
        if not commentaire.strip():
            raise ValidationError("Indiquez le motif du refus.")
        self.statut = self.Statut.REFUSEE
        self.save()
        self._journal(utilisateur, Evenement.Action.REFUS, commentaire)


class Evenement(models.Model):
    """Journal de la demande d'intervention."""

    class Action(models.TextChoices):
        PRISE_EN_CHARGE = "PRISE", "Prise en charge"
        REAFFECTATION = "REAFFECT", "Nouvelle affectation"
        REALISATION = "REALISATION", "Intervention réalisée"
        CLOTURE = "CLOTURE", "Clôture"
        REOUVERTURE = "REOUVERTURE", "Réouverture"
        REFUS = "REFUS", "Refus"

    demande = models.ForeignKey(DemandeIntervention, on_delete=models.CASCADE, related_name="evenements")
    action = models.CharField(max_length=11, choices=Action.choices)
    statut = models.CharField("statut obtenu", max_length=10, choices=DemandeIntervention.Statut.choices)
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    date = models.DateTimeField(auto_now_add=True)
    commentaire = models.TextField(blank=True)

    class Meta:
        verbose_name = "événement d'intervention"
        ordering = ["id"]
from .contrats import Contrat, Echeance  # noqa: E402,F401
