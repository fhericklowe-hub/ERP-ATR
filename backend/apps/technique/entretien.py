"""Entretien préventif : pour chaque matériel, les opérations qui reviennent (vidange, graissage, visite périodique...).

Une opération revient au bout d'un nombre d'heures, de kilomètres ou de mois, au premier des trois atteint. Quand
elle est à faire, on ouvre un ordre de réparation de type entretien ; la fin de ses travaux repousse l'échéance."""
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone

from apps.core.models import Horodate
from apps.moyens.contrats import ajouter_mois

MARGE = Decimal("0.10")   # « bientôt » : dans le dernier dixième de l'intervalle
MARGE_JOURS = 15


class PlanEntretien(Horodate):
    class Situation(models.TextChoices):
        RETARD = "RETARD", "À faire"
        PROCHE = "PROCHE", "Bientôt"
        A_VENIR = "A_VENIR", "À venir"

    materiel = models.ForeignKey("technique.Materiel", on_delete=models.PROTECT, related_name="plans", verbose_name="matériel")
    intitule = models.CharField("opération", max_length=120, help_text="Exemple : vidange moteur et filtres")
    consignes = models.TextField(blank=True, help_text="Ce qu'il faut faire, les pièces à prévoir")
    intervalle_heures = models.DecimalField("toutes les (heures)", max_digits=8, decimal_places=1, null=True, blank=True,
                                            validators=[MinValueValidator(1)])
    intervalle_km = models.PositiveIntegerField("tous les (km)", null=True, blank=True, validators=[MinValueValidator(1)])
    intervalle_mois = models.PositiveSmallIntegerField("tous les (mois)", null=True, blank=True,
                                                       validators=[MinValueValidator(1)])
    dernier_le = models.DateField("dernière réalisation")
    dernier_heures = models.DecimalField("compteur à la dernière réalisation (heures)", max_digits=10, decimal_places=1,
                                         null=True, blank=True)
    dernier_km = models.PositiveIntegerField("compteur à la dernière réalisation (km)", null=True, blank=True)
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = "plan d'entretien"
        verbose_name_plural = "plans d'entretien"
        ordering = ["materiel__code", "intitule"]

    def __str__(self):
        return f"{self.materiel.code} · {self.intitule}"

    def clean(self):
        if not (self.intervalle_heures or self.intervalle_km or self.intervalle_mois):
            raise ValidationError("Indiquez au moins une périodicité : en heures, en kilomètres ou en mois.")
        if self.dernier_le and self.dernier_le > timezone.localdate():
            raise ValidationError({"dernier_le": "La dernière réalisation ne peut pas être dans le futur."})

    def save(self, *args, **kwargs):
        # Sans relevé, on part du compteur actuel du matériel : l'intervalle court à partir de maintenant.
        if self.intervalle_heures and self.dernier_heures is None:
            self.dernier_heures = self.materiel.compteur_heures or 0
        if self.intervalle_km and self.dernier_km is None:
            self.dernier_km = self.materiel.compteur_km or 0
        super().save(*args, **kwargs)

    # ----- échéance

    @property
    def prochaine_date(self):
        return ajouter_mois(self.dernier_le, self.intervalle_mois) if self.intervalle_mois else None

    @property
    def prochaines_heures(self):
        return self.dernier_heures + self.intervalle_heures if self.intervalle_heures else None

    @property
    def prochain_km(self):
        return self.dernier_km + self.intervalle_km if self.intervalle_km else None

    def restes(self) -> list:
        """Pour chaque périodicité : (ce qu'il reste, l'intervalle, l'unité). Un reste négatif est un dépassement."""
        m, restes = self.materiel, []
        if self.intervalle_heures:
            restes.append((self.prochaines_heures - (m.compteur_heures or 0), self.intervalle_heures, "h"))
        if self.intervalle_km:
            restes.append((self.prochain_km - (m.compteur_km or 0), self.intervalle_km, "km"))
        if self.intervalle_mois:
            restes.append(((self.prochaine_date - timezone.localdate()).days, None, "j"))
        return restes

    @property
    def situation(self) -> str:
        S, proche = self.Situation, False
        for reste, intervalle, unite in self.restes():
            if reste <= 0:
                return S.RETARD
            proche = proche or reste <= (MARGE_JOURS if unite == "j" else intervalle * MARGE)
        return S.PROCHE if proche else S.A_VENIR

    # ----- ordre de réparation

    def ordre_en_cours(self):
        from .models import OrdreReparation

        S = OrdreReparation.Statut
        return self.ordres.filter(statut__in=[S.OUVERT, S.EN_COURS]).first()

    @transaction.atomic
    def ouvrir_ordre(self, utilisateur):
        from .models import Materiel, OrdreReparation

        if not utilisateur.has_perm("technique.add_ordrereparation"):
            raise PermissionDenied("Vous ne pouvez pas ouvrir d'ordre de réparation.")
        if not self.actif:
            raise ValidationError("Ce plan d'entretien n'est plus suivi.")
        if self.materiel.etat == Materiel.Etat.REFORME:
            raise ValidationError("Ce matériel est réformé.")
        en_cours = self.ordre_en_cours()
        if en_cours:
            raise ValidationError(f"L'ordre {en_cours.numero} est déjà ouvert pour cet entretien.")
        description = self.intitule + (f"\n{self.consignes}" if self.consignes else "")
        return OrdreReparation.objects.create(
            materiel=self.materiel, type=OrdreReparation.Type.PREVENTIF, immobilisant=False, description=description,
            plan=self, demandeur=utilisateur, cree_par=utilisateur, modifie_par=utilisateur)

    def enregistrer_realisation(self, ordre):
        """Appelé à la fin des travaux de l'ordre : l'échéance repart de ce jour et du compteur relevé."""
        m = self.materiel
        self.dernier_le = timezone.localdate()
        if self.intervalle_heures:
            self.dernier_heures = ordre.compteur_heures if ordre.compteur_heures is not None else (m.compteur_heures or 0)
        if self.intervalle_km:
            self.dernier_km = ordre.compteur_km if ordre.compteur_km is not None else (m.compteur_km or 0)
        self.save()
