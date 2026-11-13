"""Technique : le parc de matériels (engins de manutention et de levage, camions, véhicules) et les ordres de
réparation (OR). Les pièces sorties du stock pour un OR s'y rattachent par le numéro d'OR du bon de sortie."""
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.achats.choix import Activite
from apps.core.models import Compteur, Horodate, Site
from apps.referentiels.models import Emplacement


class Materiel(Horodate):
    class Type(models.TextChoices):
        CHARIOT = "CHARIOT", "Chariot élévateur"
        GRUE = "GRUE", "Grue"
        NACELLE = "NACELLE", "Nacelle"
        CAMION = "CAMION", "Camion"
        TRACTEUR = "TRACTEUR", "Tracteur routier"
        REMORQUE = "REMORQUE", "Remorque ou semi-remorque"
        VEHICULE = "VEHICULE", "Véhicule léger"
        GROUPE = "GROUPE", "Groupe électrogène ou compresseur"
        AUTRE = "AUTRE", "Autre"

    class Etat(models.TextChoices):
        DISPONIBLE = "DISPONIBLE", "Disponible"
        EN_EXPLOITATION = "EXPLOITE", "En exploitation ou en location"
        EN_PANNE = "EN_PANNE", "En panne"
        EN_REPARATION = "REPARATION", "En réparation"
        REFORME = "REFORME", "Réformé ou vendu"

    code = models.CharField("n° de parc", max_length=30, unique=True)
    type = models.CharField(max_length=10, choices=Type.choices)
    designation = models.CharField("désignation", max_length=150)
    marque = models.CharField(max_length=60, blank=True)
    modele = models.CharField("modèle", max_length=60, blank=True)
    numero_serie = models.CharField("n° de série", max_length=60, blank=True)
    immatriculation = models.CharField(max_length=30, blank=True)
    annee = models.PositiveSmallIntegerField("année", null=True, blank=True)
    capacite = models.CharField("capacité", max_length=40, blank=True, help_text="Exemple : 3,5 t ; 50 t ; 12 m")
    activite = models.CharField("activité", max_length=11, choices=Activite.choices, blank=True)
    site = models.ForeignKey(Site, on_delete=models.PROTECT, related_name="materiels", verbose_name="site de rattachement")
    emplacement = models.ForeignKey(Emplacement, null=True, blank=True, on_delete=models.PROTECT, related_name="materiels",
                                    verbose_name="où il se trouve", help_text="Un site de l'entreprise ou un site client")
    etat = models.CharField("état", max_length=10, choices=Etat.choices, default=Etat.DISPONIBLE)
    compteur_heures = models.DecimalField("compteur (heures)", max_digits=10, decimal_places=1, null=True, blank=True)
    compteur_km = models.PositiveIntegerField("compteur (km)", null=True, blank=True)
    date_mise_en_service = models.DateField("mise en service", null=True, blank=True)
    observations = models.TextField(blank=True)

    class Meta:
        verbose_name = "matériel"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} · {self.designation}"

    def suivre_les_reparations(self):
        """Met l'état à jour d'après les OR ouverts, sans toucher à un matériel réformé."""
        if self.etat == self.Etat.REFORME:
            return
        S = OrdreReparation.Statut
        ouverts = self.ordres.filter(statut__in=[S.OUVERT, S.EN_COURS], immobilisant=True)
        if ouverts.filter(statut=S.EN_COURS).exists():
            etat = self.Etat.EN_REPARATION
        elif ouverts.exists():
            etat = self.Etat.EN_PANNE
        elif self.etat in (self.Etat.EN_PANNE, self.Etat.EN_REPARATION):
            # Réparé chez le client : il reprend son exploitation, sinon il redevient disponible.
            chez_un_client = hasattr(self, "mises_a_disposition") and self.mises_a_disposition.filter(statut="EN_COURS").exists()
            etat = self.Etat.EN_EXPLOITATION if chez_un_client else self.Etat.DISPONIBLE
        else:
            return
        if etat != self.etat:
            self.etat = etat
            self.save(update_fields=["etat", "modifie_le"])


class OrdreReparation(Horodate):
    class Type(models.TextChoices):
        CORRECTIF = "CORRECTIF", "Panne (correctif)"
        PREVENTIF = "PREVENTIF", "Entretien (préventif)"
        ACCIDENT = "ACCIDENT", "Accident ou casse"
        AMELIORATION = "AMELIO", "Modification ou amélioration"

    class Statut(models.TextChoices):
        OUVERT = "OUVERT", "Ouvert"
        EN_COURS = "EN_COURS", "En cours"
        TERMINE = "TERMINE", "Travaux terminés, à clôturer"
        CLOTURE = "CLOTURE", "Clôturé"
        ANNULE = "ANNULE", "Annulé"

    numero = models.CharField("n° d'OR", max_length=20, unique=True, editable=False)
    statut = models.CharField(max_length=8, choices=Statut.choices, default=Statut.OUVERT, editable=False)
    materiel = models.ForeignKey(Materiel, on_delete=models.PROTECT, related_name="ordres", verbose_name="matériel")
    type = models.CharField(max_length=9, choices=Type.choices, default=Type.CORRECTIF)
    immobilisant = models.BooleanField("le matériel est immobilisé", default=True)
    description = models.TextField("panne constatée ou travaux demandés")
    plan = models.ForeignKey("technique.PlanEntretien", null=True, blank=True, editable=False, on_delete=models.SET_NULL,
                             related_name="ordres", verbose_name="plan d'entretien")
    demandeur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ordres_demandes")
    mecanicien = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
                                   related_name="ordres_confies", verbose_name="mécanicien")
    compteur_heures = models.DecimalField("compteur relevé (heures)", max_digits=10, decimal_places=1, null=True, blank=True)
    compteur_km = models.PositiveIntegerField("compteur relevé (km)", null=True, blank=True)
    diagnostic = models.TextField(blank=True)
    travaux = models.TextField("travaux réalisés", blank=True)
    demarre_le = models.DateTimeField("démarré le", null=True, blank=True, editable=False)
    termine_le = models.DateTimeField("terminé le", null=True, blank=True, editable=False)
    cloture_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, editable=False,
                                    on_delete=models.PROTECT, related_name="+")
    cloture_le = models.DateTimeField("clôturé le", null=True, blank=True, editable=False)
    motif_annulation = models.TextField("motif de l'annulation", blank=True, editable=False)

    class Meta:
        verbose_name = "ordre de réparation"
        verbose_name_plural = "ordres de réparation"
        ordering = ["-cree_le"]
        permissions = [("piloter_ordrereparation", "Peut affecter, clôturer, rouvrir et annuler un ordre de réparation"),
                       ("voir_couts_ordrereparation", "Peut voir le coût d'un ordre de réparation")]

    def __str__(self):
        return self.numero

    @transaction.atomic
    def save(self, *args, **kwargs):
        if not self.numero:
            annee = timezone.localdate().year
            self.numero = f"OR-{annee}-{Compteur.suivant(f'OR-{annee}'):04d}"
        super().save(*args, **kwargs)
        self.materiel.suivre_les_reparations()

    # ----- qui peut quoi

    @property
    def ouvert(self) -> bool:
        return self.statut in (self.Statut.OUVERT, self.Statut.EN_COURS)

    def pilote(self, u) -> bool:
        return u.has_perm("technique.piloter_ordrereparation")

    def peut_travailler(self, u) -> bool:
        """Le mécanicien désigné, ou à défaut tout mécanicien, et le chef d'atelier."""
        return self.ouvert and u.has_perm("technique.change_ordrereparation") and (
            self.pilote(u) or self.mecanicien_id in (None, u.id))

    # ----- circuit

    def _relever(self, heures, km):
        """Reporte le compteur relevé sur la fiche du matériel, s'il avance."""
        m, champs = self.materiel, []
        if heures is not None:
            self.compteur_heures = heures
            if m.compteur_heures is None or heures > m.compteur_heures:
                m.compteur_heures = heures
                champs.append("compteur_heures")
        if km is not None:
            self.compteur_km = km
            if m.compteur_km is None or km > m.compteur_km:
                m.compteur_km = km
                champs.append("compteur_km")
        if champs:
            m.save(update_fields=champs + ["modifie_le"])

    def affecter(self, utilisateur, mecanicien):
        if not self.pilote(utilisateur):
            raise PermissionDenied("Seul le chef d'atelier affecte un ordre de réparation.")
        if not self.ouvert:
            raise ValidationError("Cet ordre de réparation n'est plus ouvert.")
        self.mecanicien, self.modifie_par = mecanicien, utilisateur
        self.save()

    @transaction.atomic
    def demarrer(self, utilisateur, diagnostic="", heures=None, km=None):
        if self.statut != self.Statut.OUVERT:
            raise ValidationError("Les travaux sont déjà démarrés ou l'ordre est fermé.")
        if not self.peut_travailler(utilisateur):
            raise PermissionDenied("Cet ordre de réparation est confié à un autre mécanicien.")
        self.statut, self.demarre_le = self.Statut.EN_COURS, timezone.now()
        if not self.mecanicien_id and not self.pilote(utilisateur):
            self.mecanicien = utilisateur
        if diagnostic.strip():
            self.diagnostic = diagnostic.strip()
        self._relever(heures, km)
        self.modifie_par = utilisateur
        self.save()

    @transaction.atomic
    def terminer(self, utilisateur, travaux, heures=None, km=None):
        if self.statut != self.Statut.EN_COURS:
            raise ValidationError("Les travaux ne sont pas en cours.")
        if not self.peut_travailler(utilisateur):
            raise PermissionDenied("Cet ordre de réparation est confié à un autre mécanicien.")
        if not travaux.strip():
            raise ValidationError("Décrivez les travaux réalisés.")
        self.statut, self.termine_le, self.travaux = self.Statut.TERMINE, timezone.now(), travaux.strip()
        self._relever(heures, km)
        self.modifie_par = utilisateur
        self.save()
        if self.plan_id:
            self.plan.enregistrer_realisation(self)

    def cloturer(self, utilisateur):
        if not self.pilote(utilisateur):
            raise PermissionDenied("Seul le chef d'atelier clôture un ordre de réparation.")
        if self.statut != self.Statut.TERMINE:
            raise ValidationError("Les travaux doivent être terminés avant la clôture.")
        self.statut, self.cloture_par, self.cloture_le = self.Statut.CLOTURE, utilisateur, timezone.now()
        self.modifie_par = utilisateur
        self.save()

    def rouvrir(self, utilisateur, commentaire):
        if not self.pilote(utilisateur):
            raise PermissionDenied("Seul le chef d'atelier rouvre un ordre de réparation.")
        if self.statut not in (self.Statut.TERMINE, self.Statut.CLOTURE):
            raise ValidationError("Seul un ordre terminé ou clôturé se rouvre.")
        if not commentaire.strip():
            raise ValidationError("Indiquez pourquoi l'ordre est rouvert.")
        self.statut, self.termine_le, self.cloture_par, self.cloture_le = self.Statut.EN_COURS, None, None, None
        self.travaux = f"{self.travaux}\n[Rouvert le {timezone.localdate():%d/%m/%Y} : {commentaire.strip()}]".strip()
        self.modifie_par = utilisateur
        self.save()

    def annuler(self, utilisateur, commentaire):
        if not self.pilote(utilisateur):
            raise PermissionDenied("Seul le chef d'atelier annule un ordre de réparation.")
        if not self.ouvert:
            raise ValidationError("Cet ordre de réparation n'est plus ouvert.")
        if not commentaire.strip():
            raise ValidationError("Indiquez le motif de l'annulation.")
        if self.sorties().exists():
            raise ValidationError("Des pièces sont sorties du stock pour cet ordre : il ne peut plus être annulé.")
        self.statut, self.motif_annulation, self.modifie_par = self.Statut.ANNULE, commentaire.strip(), utilisateur
        self.save()

    # ----- temps passé

    def peut_saisir_temps(self, u) -> bool:
        """Tant que l'ordre n'est pas clôturé : tout mécanicien pour ses heures, le chef d'atelier pour tous."""
        return self.statut in (self.Statut.EN_COURS, self.Statut.TERMINE) and u.has_perm("technique.change_ordrereparation")

    def saisir_temps(self, utilisateur, heures, date=None, mecanicien=None, commentaire=""):
        from .couts import ReglageAtelier, TempsPasse

        if self.statut not in (self.Statut.EN_COURS, self.Statut.TERMINE):
            raise ValidationError("Le temps se saisit sur un ordre démarré et pas encore clôturé.")
        if not self.peut_saisir_temps(utilisateur):
            raise PermissionDenied("Vous ne pouvez pas saisir de temps sur cet ordre de réparation.")
        mecanicien = mecanicien or utilisateur
        if mecanicien != utilisateur and not self.pilote(utilisateur):
            raise PermissionDenied("Seul le chef d'atelier saisit le temps d'un autre mécanicien.")
        date = date or timezone.localdate()
        if date > timezone.localdate():
            raise ValidationError("La date ne peut pas être dans le futur.")
        if date < timezone.localtime(self.cree_le).date():
            raise ValidationError("La date est antérieure à l'ouverture de l'ordre.")
        temps = TempsPasse(ordre=self, mecanicien=mecanicien, date=date, heures=heures, taux_horaire=ReglageAtelier.taux(),
                           commentaire=commentaire.strip()[:200], saisi_par=utilisateur)
        temps.full_clean()
        deja = sum(t.heures for t in self.temps.model.objects.filter(mecanicien=mecanicien, date=date))
        if deja + heures > 24:
            raise ValidationError(f"{mecanicien} aurait plus de 24 heures saisies le {date:%d/%m/%Y}.")
        temps.save()
        return temps

    def retirer_temps(self, utilisateur, temps):
        if self.statut == self.Statut.CLOTURE:
            raise ValidationError("L'ordre est clôturé : le temps saisi ne se modifie plus.")
        if not (self.pilote(utilisateur) or (temps.saisi_par_id == utilisateur.id and self.peut_saisir_temps(utilisateur))):
            raise PermissionDenied("Seuls l'auteur de la saisie et le chef d'atelier peuvent la retirer.")
        temps.delete()

    def sorties(self):
        """Bons de sortie validés qui portent ce numéro d'OR."""
        from apps.stock.models import BonSortie

        return BonSortie.objects.filter(numero_or__iexact=self.numero, statut=BonSortie.Statut.VALIDE)


from .couts import ReglageAtelier, TempsPasse  # noqa: E402,F401  (modèles déclarés dans couts.py)
from .entretien import PlanEntretien  # noqa: E402,F401
