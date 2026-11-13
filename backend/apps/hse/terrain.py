"""HSE sur le terrain : les visites de sécurité (ce qui a été constaté, et les actions qui en découlent) et les
équipements de protection individuelle remis à chaque salarié, avec leur date de renouvellement."""
import datetime

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.core.models import Compteur, Horodate, Site


class Visite(Horodate):
    class Statut(models.TextChoices):
        OUVERTE = "OUVERTE", "Actions en cours"
        CLOSE = "CLOSE", "Close"

    numero = models.CharField("n°", max_length=20, unique=True, editable=False)
    statut = models.CharField(max_length=7, choices=Statut.choices, default=Statut.OUVERTE, editable=False)
    date = models.DateField(default=timezone.localdate)
    site = models.ForeignKey(Site, on_delete=models.PROTECT, related_name="visites_hse")
    lieu = models.CharField("lieu ou activité visités", max_length=200)
    participants = models.CharField(max_length=300, blank=True)
    visiteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="visites_hse", verbose_name="visite menée par")
    points_positifs = models.TextField("bonnes pratiques constatées", blank=True)
    ecarts = models.TextField("écarts constatés", blank=True)
    clos_le = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "visite de sécurité"
        verbose_name_plural = "visites de sécurité"
        ordering = ["-date", "-id"]

    def __str__(self):
        return self.numero

    def clean(self):
        if self.date and self.date > timezone.localdate():
            raise ValidationError({"date": "La visite ne peut pas être dans le futur."})
        if not (self.points_positifs or "").strip() and not (self.ecarts or "").strip():
            raise ValidationError({"ecarts": "Notez au moins un constat : une bonne pratique ou un écart."})

    @transaction.atomic
    def save(self, *args, **kwargs):
        if not self.numero:
            annee = timezone.localdate().year
            self.numero = f"VS-{annee}-{Compteur.suivant(f'VS-{annee}'):04d}"
        super().save(*args, **kwargs)

    def _exiger(self, utilisateur):
        if not utilisateur.has_perm("hse.traiter_evenement"):
            raise PermissionDenied("Seul le responsable HSE clôt ou rouvre une visite.")

    def clore(self, utilisateur):
        self._exiger(utilisateur)
        if self.statut == self.Statut.CLOSE:
            raise ValidationError("Cette visite est déjà close.")
        if self.actions.filter(statut="A_FAIRE").exists():
            raise ValidationError("Des actions restent à faire : terminez-les ou abandonnez-les avant de clore.")
        self.statut, self.clos_le, self.modifie_par = self.Statut.CLOSE, timezone.now(), utilisateur
        self.save()

    def rouvrir(self, utilisateur):
        self._exiger(utilisateur)
        if self.statut != self.Statut.CLOSE:
            raise ValidationError("Cette visite n'est pas close.")
        self.statut, self.clos_le, self.modifie_par = self.Statut.OUVERTE, None, utilisateur
        self.save()


class DotationEPI(Horodate):
    class Equipement(models.TextChoices):
        CASQUE = "CASQUE", "Casque"
        CHAUSSURES = "CHAUSSURES", "Chaussures de sécurité"
        GANTS = "GANTS", "Gants"
        GILET = "GILET", "Gilet haute visibilité"
        LUNETTES = "LUNETTES", "Lunettes de protection"
        AUDITIF = "AUDITIF", "Protections auditives"
        MASQUE = "MASQUE", "Masque"
        HARNAIS = "HARNAIS", "Harnais antichute"
        TENUE = "TENUE", "Tenue de travail"
        AUTRE = "AUTRE", "Autre"

    salarie = models.ForeignKey("rh.Salarie", on_delete=models.PROTECT, related_name="dotations_epi", verbose_name="salarié")
    equipement = models.CharField("équipement", max_length=10, choices=Equipement.choices)
    precision = models.CharField("modèle, taille ou pointure", max_length=100, blank=True)
    quantite = models.PositiveSmallIntegerField("quantité", default=1)
    date_remise = models.DateField("remis le", default=timezone.localdate)
    a_renouveler_le = models.DateField("à renouveler le", null=True, blank=True)
    remis_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    observations = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "dotation d'EPI"
        verbose_name_plural = "dotations d'EPI"
        ordering = ["-date_remise", "-id"]

    def __str__(self):
        return f"{self.get_equipement_display()} · {self.salarie}"

    def clean(self):
        if self.date_remise and self.date_remise > timezone.localdate():
            raise ValidationError({"date_remise": "La remise ne peut pas être dans le futur."})
        if self.a_renouveler_le and self.date_remise and self.a_renouveler_le <= self.date_remise:
            raise ValidationError({"a_renouveler_le": "Le renouvellement vient après la remise."})
        if not self.quantite:
            raise ValidationError({"quantite": "La quantité doit être positive."})


def renouvellements(jours=30) -> list:
    """EPI des salariés en poste dont le renouvellement arrive dans le délai, ou est dépassé. Un équipement remis à
    nouveau depuis (même salarié, même équipement) n'est plus signalé."""
    aujourd_hui = timezone.localdate()
    limite = aujourd_hui + datetime.timedelta(days=jours)
    dernieres = {}
    for d in DotationEPI.objects.filter(salarie__statut="ACTIF").select_related("salarie__site").order_by("date_remise", "id"):
        dernieres[d.salarie_id, d.equipement] = d
    return sorted((d for d in dernieres.values() if d.a_renouveler_le and d.a_renouveler_le <= limite),
                  key=lambda d: (d.a_renouveler_le, str(d.salarie)))
