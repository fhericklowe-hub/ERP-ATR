"""Fiche GO / NO GO : avant de faire un devis, le commercial fait valider l'opportunité.

Circuit : le commercial soumet sa fiche, puis le responsable commercial, la finance et enfin le DG la valident, chacun à son
tour. Un refus à l'une des étapes donne un NO GO (motif obligatoire) ; une fiche peut aussi être renvoyée au commercial pour
correction. Le devis ne peut se faire que sur une fiche « GO »."""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.achats.choix import Activite
from apps.core import devises
from apps.core.models import Compteur, Horodate, Site
from apps.referentiels.models import Tiers


class Opportunite(Horodate):
    class Statut(models.TextChoices):
        BROUILLON = "BROUILLON", "Brouillon"
        ATT_RESPONSABLE = "ATT_RESP", "En attente du responsable commercial"
        ATT_FINANCE = "ATT_FIN", "En attente de la finance"
        ATT_DG = "ATT_DG", "En attente du DG"
        GO = "GO", "GO"
        NO_GO = "NO_GO", "NO GO"
        ANNULEE = "ANNULEE", "Annulée"

    class Type(models.TextChoices):
        LOCATION = "LOCATION", "Location de matériel"
        TRANSPORT = "TRANSPORT", "Transport"
        PRESTATION = "PRESTATION", "Prestation (manutention, levage…)"
        VENTE = "VENTE", "Vente"
        AUTRE = "AUTRE", "Autre"

    class Origine(models.TextChoices):
        APPEL_OFFRES = "APPEL_OFFRES", "Appel d'offres"
        CLIENT = "CLIENT", "Client existant"
        PROSPECTION = "PROSPECTION", "Prospection"
        RECOMMANDATION = "RECOMMANDATION", "Recommandation"
        AUTRE = "AUTRE", "Autre"

    class Phase(models.TextChoices):
        IDENTIFICATION = "IDENTIFICATION", "Identification"
        QUALIFICATION = "QUALIFICATION", "Qualification"
        OFFRE = "OFFRE", "Offre à remettre"
        NEGOCIATION = "NEGOCIATION", "Négociation"

    numero = models.CharField("n° de fiche", max_length=20, unique=True, editable=False)
    statut = models.CharField(max_length=9, choices=Statut.choices, default=Statut.BROUILLON, editable=False)
    nom_affaire = models.CharField("nom de l'affaire", max_length=200)
    client = models.ForeignKey(Tiers, on_delete=models.PROTECT, related_name="opportunites", limit_choices_to={"est_client": True})
    site = models.ForeignKey(Site, on_delete=models.PROTECT, related_name="opportunites", verbose_name="agence")
    commercial = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="opportunites", verbose_name="commercial")
    activite = models.CharField("activité", max_length=12, choices=Activite.choices, blank=True)
    type_affaire = models.CharField("type d'affaire", max_length=10, choices=Type.choices, default=Type.LOCATION)
    origine = models.CharField("origine de l'affaire", max_length=14, choices=Origine.choices, default=Origine.CLIENT)
    phase = models.CharField("phase de vente", max_length=14, choices=Phase.choices, default=Phase.QUALIFICATION)
    probabilite = models.PositiveSmallIntegerField("probabilité (%)", null=True, blank=True)
    devise = models.CharField(max_length=3, choices=devises.CHOIX, default="XOF")
    ca_previsionnel = models.DecimalField("CA prévisionnel", max_digits=16, decimal_places=2)
    marge_previsionnelle = models.DecimalField("marge brute prévisionnelle", max_digits=16, decimal_places=2)
    ca_services = models.DecimalField("dont CA prestations", max_digits=16, decimal_places=2, null=True, blank=True)
    marge_services = models.DecimalField("dont marge prestations", max_digits=16, decimal_places=2, null=True, blank=True)
    ca_materiel = models.DecimalField("dont CA matériel / location", max_digits=16, decimal_places=2, null=True, blank=True)
    marge_materiel = models.DecimalField("dont marge matériel / location", max_digits=16, decimal_places=2, null=True, blank=True)
    lieu = models.CharField("lieu d'intervention", max_length=200, blank=True)
    date_prise_commande = models.DateField("date prévue de prise de commande", null=True, blank=True)
    prochaine_etape = models.CharField("prochaine étape", max_length=200, blank=True)
    reference_ao = models.CharField("référence de l'appel d'offres", max_length=100, blank=True)
    date_lancement_ao = models.DateField("lancement de l'appel d'offres", null=True, blank=True)
    date_limite_ao = models.DateField("date limite de remise", null=True, blank=True)
    partenaire = models.CharField("partenaire ou sous-traitant principal", max_length=150, blank=True)
    part_partenaire = models.DecimalField("part du partenaire (%)", max_digits=5, decimal_places=2, null=True, blank=True)
    risques = models.TextField("risques identifiés", blank=True)
    observations = models.TextField("observations", blank=True)

    class Meta:
        verbose_name = "fiche GO / NO GO"
        verbose_name_plural = "fiches GO / NO GO"
        ordering = ["-cree_le"]
        permissions = [
            ("valider_responsable_opportunite", "Peut valider une fiche GO / NO GO (responsable commercial)"),
            ("valider_finance_opportunite", "Peut valider une fiche GO / NO GO (finance)"),
            ("valider_dg_opportunite", "Peut valider une fiche GO / NO GO (DG)"),
        ]
        constraints = [
            models.CheckConstraint(name="opportunite_ca_positif", condition=models.Q(ca_previsionnel__gt=0)),
            models.CheckConstraint(name="opportunite_probabilite_valide", condition=models.Q(probabilite__isnull=True) | models.Q(probabilite__lte=100)),
        ]

    def __str__(self):
        return f"{self.numero} {self.nom_affaire}"

    @transaction.atomic
    def save(self, *args, **kwargs):
        if not self.numero:
            annee = timezone.localdate().year
            self.numero = f"GNG-{annee}-{Compteur.suivant(f'GNG-{annee}'):04d}"
        super().save(*args, **kwargs)

    @property
    def taux_marge(self):
        return (self.marge_previsionnelle / self.ca_previsionnel * 100).quantize(Decimal("0.1")) if self.ca_previsionnel else None

    @property
    def modifiable(self) -> bool:
        return self.statut == self.Statut.BROUILLON

    # ----- qui peut quoi

    DROIT_ETAPE = {
        Statut.ATT_RESPONSABLE: ("commercial.valider_responsable_opportunite", "le responsable commercial"),
        Statut.ATT_FINANCE: ("commercial.valider_finance_opportunite", "la finance"),
        Statut.ATT_DG: ("commercial.valider_dg_opportunite", "le DG"),
    }
    SUIVANT = {Statut.ATT_RESPONSABLE: Statut.ATT_FINANCE, Statut.ATT_FINANCE: Statut.ATT_DG, Statut.ATT_DG: Statut.GO}

    def peut_preparer(self, u) -> bool:
        """Le commercial de la fiche, ou le responsable commercial."""
        return u.has_perm("commercial.gerer_devis") or (u.has_perm("commercial.change_opportunite") and self.commercial_id == u.id)

    def peut_decider(self, u) -> bool:
        droit = self.DROIT_ETAPE.get(self.statut)
        return bool(droit) and u.has_perm(droit[0])

    def _noter(self, utilisateur, action, commentaire="", niveau=""):
        self.decisions.create(auteur=utilisateur, action=action, niveau=niveau, commentaire=commentaire.strip(), statut=self.statut)

    # ----- circuit

    @transaction.atomic
    def soumettre(self, utilisateur):
        if not self.peut_preparer(utilisateur):
            raise PermissionDenied("Cette fiche est suivie par un autre commercial.")
        if self.statut != self.Statut.BROUILLON:
            raise ValidationError("Cette fiche n'est plus un brouillon.")
        self.statut, self.modifie_par = self.Statut.ATT_RESPONSABLE, utilisateur
        self.save()
        self._noter(utilisateur, "SOUMIS")

    @transaction.atomic
    def valider(self, utilisateur, commentaire=""):
        if self.statut not in self.DROIT_ETAPE:
            raise ValidationError("Cette fiche n'attend aucune validation.")
        if not self.peut_decider(utilisateur):
            raise PermissionDenied(f"Seul {self.DROIT_ETAPE[self.statut][1]} peut valider cette étape.")
        niveau = self.statut
        self.statut, self.modifie_par = self.SUIVANT[self.statut], utilisateur
        self.save()
        self._noter(utilisateur, "VALIDE", commentaire, niveau)

    @transaction.atomic
    def refuser(self, utilisateur, commentaire=""):
        """NO GO : l'affaire est abandonnée."""
        if self.statut not in self.DROIT_ETAPE:
            raise ValidationError("Cette fiche n'attend aucune validation.")
        if not self.peut_decider(utilisateur):
            raise PermissionDenied(f"Seul {self.DROIT_ETAPE[self.statut][1]} peut se prononcer à cette étape.")
        if not commentaire.strip():
            raise ValidationError("Indiquez le motif du NO GO.")
        niveau = self.statut
        self.statut, self.modifie_par = self.Statut.NO_GO, utilisateur
        self.save()
        self._noter(utilisateur, "REFUSE", commentaire, niveau)

    @transaction.atomic
    def renvoyer(self, utilisateur, commentaire=""):
        """Retour au commercial pour compléter ou corriger la fiche."""
        if self.statut not in self.DROIT_ETAPE:
            raise ValidationError("Cette fiche n'attend aucune validation.")
        if not self.peut_decider(utilisateur):
            raise PermissionDenied(f"Seul {self.DROIT_ETAPE[self.statut][1]} peut renvoyer la fiche à cette étape.")
        if not commentaire.strip():
            raise ValidationError("Indiquez ce qu'il faut corriger ou compléter.")
        niveau = self.statut
        self.statut, self.modifie_par = self.Statut.BROUILLON, utilisateur
        self.save()
        self._noter(utilisateur, "RENVOYE", commentaire, niveau)

    @transaction.atomic
    def annuler(self, utilisateur, commentaire=""):
        if not self.peut_preparer(utilisateur):
            raise PermissionDenied("Cette fiche est suivie par un autre commercial.")
        if self.statut in (self.Statut.NO_GO, self.Statut.ANNULEE):
            raise ValidationError("Cette fiche est déjà close.")
        if self.statut == self.Statut.GO and self.devis.exclude(statut="ANNULE").exists():
            raise ValidationError("Des devis sont établis sur cette fiche : annulez-les d'abord.")
        if not commentaire.strip():
            raise ValidationError("Indiquez le motif de l'annulation.")
        self.statut, self.modifie_par = self.Statut.ANNULEE, utilisateur
        self.save()
        self._noter(utilisateur, "ANNULE", commentaire)


class DecisionOpportunite(models.Model):
    """Historique d'une fiche : chaque étape, avec son auteur et son commentaire."""

    opportunite = models.ForeignKey(Opportunite, on_delete=models.CASCADE, related_name="decisions")
    date = models.DateTimeField(auto_now_add=True)
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    action = models.CharField(max_length=8)   # SOUMIS, VALIDE, REFUSE, RENVOYE, ANNULE
    niveau = models.CharField(max_length=9, blank=True)   # l'étape où la décision a été prise
    commentaire = models.TextField(blank=True)
    statut = models.CharField("statut obtenu", max_length=9, choices=Opportunite.Statut.choices)

    class Meta:
        ordering = ["date", "id"]
