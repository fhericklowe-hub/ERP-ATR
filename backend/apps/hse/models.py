"""HSE : la déclaration d'un événement (accident, presqu'accident, incident, situation dangereuse), son analyse par
le responsable HSE et les actions correctives qui en découlent, suivies jusqu'à leur réalisation."""
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.core.models import Compteur, Horodate, Site


class Evenement(Horodate):
    class Type(models.TextChoices):
        ACCIDENT = "ACCIDENT", "Accident du travail"
        PRESQUE = "PRESQUE", "Presqu'accident"
        SOIN = "SOIN", "Premiers soins"
        MATERIEL = "MATERIEL", "Dégât matériel"
        ENVIRONNEMENT = "ENVIRON", "Atteinte à l'environnement"
        DANGER = "DANGER", "Situation dangereuse"

    class Gravite(models.TextChoices):
        MINEURE = "1", "Mineure"
        SERIEUSE = "2", "Sérieuse"
        GRAVE = "3", "Grave"

    class Statut(models.TextChoices):
        DECLARE = "DECLARE", "Déclaré"
        ANALYSE = "ANALYSE", "En cours de traitement"
        CLOS = "CLOS", "Clos"

    numero = models.CharField("n°", max_length=20, unique=True, editable=False)
    statut = models.CharField(max_length=7, choices=Statut.choices, default=Statut.DECLARE, editable=False)
    type = models.CharField(max_length=8, choices=Type.choices)
    gravite = models.CharField("gravité", max_length=1, choices=Gravite.choices, default=Gravite.MINEURE)
    date = models.DateTimeField("date et heure de l'événement")
    site = models.ForeignKey(Site, on_delete=models.PROTECT, related_name="evenements_hse")
    lieu = models.CharField("lieu précis", max_length=200, blank=True, help_text="Atelier, quai, chantier du client...")
    description = models.TextField("ce qui s'est passé")
    personnes = models.CharField("personnes concernées", max_length=300, blank=True)
    materiel = models.ForeignKey("technique.Materiel", null=True, blank=True, on_delete=models.PROTECT, related_name="evenements_hse",
                                 verbose_name="matériel en cause")
    mesures_immediates = models.TextField("mesures prises sur le moment", blank=True)
    jours_arret = models.PositiveSmallIntegerField("jours d'arrêt de travail", default=0)
    declarant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="evenements_hse", verbose_name="déclaré par")

    causes = models.TextField("analyse des causes", blank=True, editable=False)
    conclusion = models.TextField("conclusion", blank=True, editable=False)
    clos_le = models.DateTimeField("clos le", null=True, blank=True, editable=False)
    clos_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, editable=False, on_delete=models.PROTECT, related_name="+")

    class Meta:
        verbose_name = "événement HSE"
        verbose_name_plural = "événements HSE"
        ordering = ["-date", "-id"]
        permissions = [("traiter_evenement", "Peut analyser et clore les événements HSE et voir toutes les déclarations")]

    def __str__(self):
        return self.numero

    def clean(self):
        if self.date and self.date > timezone.now():
            raise ValidationError({"date": "L'événement ne peut pas être dans le futur."})
        if self.jours_arret and self.type != self.Type.ACCIDENT:
            raise ValidationError({"jours_arret": "Les jours d'arrêt concernent un accident du travail."})

    @transaction.atomic
    def save(self, *args, **kwargs):
        if not self.numero:
            annee = timezone.localdate().year
            self.numero = f"HSE-{annee}-{Compteur.suivant(f'HSE-{annee}'):04d}"
        super().save(*args, **kwargs)

    # ----- circuit

    def _exiger(self, utilisateur, ouvert=True):
        if not utilisateur.has_perm("hse.traiter_evenement"):
            raise PermissionDenied("Seul le responsable HSE traite les événements.")
        if ouvert and self.statut == self.Statut.CLOS:
            raise ValidationError("Cet événement est clos. Rouvrez-le d'abord.")

    def analyser(self, utilisateur, causes, gravite=None, jours_arret=None):
        """Enregistre l'analyse des causes ; le responsable HSE peut corriger la gravité et les jours d'arrêt."""
        self._exiger(utilisateur)
        if not (causes or "").strip():
            raise ValidationError("Décrivez les causes de l'événement.")
        if gravite:
            if gravite not in self.Gravite.values:
                raise ValidationError("Gravité inconnue.")
            self.gravite = gravite
        if jours_arret is not None:
            if jours_arret and self.type != self.Type.ACCIDENT:
                raise ValidationError("Les jours d'arrêt concernent un accident du travail.")
            self.jours_arret = jours_arret
        self.causes, self.statut, self.modifie_par = causes.strip(), self.Statut.ANALYSE, utilisateur
        self.save()

    def clore(self, utilisateur, conclusion):
        self._exiger(utilisateur)
        if not self.causes:
            raise ValidationError("Enregistrez l'analyse des causes avant de clore.")
        if self.actions.filter(statut=ActionCorrective.Statut.A_FAIRE).exists():
            raise ValidationError("Des actions correctives restent à faire : terminez-les ou abandonnez-les avant de clore.")
        if not (conclusion or "").strip():
            raise ValidationError("Rédigez la conclusion.")
        self.statut, self.conclusion, self.clos_le, self.clos_par = self.Statut.CLOS, conclusion.strip(), timezone.now(), utilisateur
        self.modifie_par = utilisateur
        self.save()

    def rouvrir(self, utilisateur):
        self._exiger(utilisateur, ouvert=False)
        if self.statut != self.Statut.CLOS:
            raise ValidationError("Cet événement n'est pas clos.")
        self.statut, self.clos_le, self.clos_par, self.modifie_par = self.Statut.ANALYSE, None, None, utilisateur
        self.save()


class ActionCorrective(Horodate):
    class Statut(models.TextChoices):
        A_FAIRE = "A_FAIRE", "À faire"
        FAITE = "FAITE", "Faite"
        ABANDONNEE = "ABANDON", "Abandonnée"

    evenement = models.ForeignKey(Evenement, null=True, blank=True, on_delete=models.CASCADE, related_name="actions", verbose_name="événement")
    visite = models.ForeignKey("hse.Visite", null=True, blank=True, on_delete=models.CASCADE, related_name="actions",
                               verbose_name="visite de sécurité")
    statut = models.CharField(max_length=7, choices=Statut.choices, default=Statut.A_FAIRE, editable=False)
    description = models.CharField("action", max_length=300)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="actions_hse")
    echeance = models.DateField("à faire avant le")
    faite_le = models.DateField("faite le", null=True, blank=True, editable=False)
    commentaire = models.TextField(blank=True, editable=False)

    class Meta:
        verbose_name = "action corrective"
        verbose_name_plural = "actions correctives"
        ordering = ["echeance", "id"]
        constraints = [models.CheckConstraint(
            name="action_evenement_ou_visite",
            condition=models.Q(evenement__isnull=False, visite__isnull=True) | models.Q(evenement__isnull=True, visite__isnull=False))]

    def __str__(self):
        return self.description

    @property
    def origine(self):
        """L'événement ou la visite d'où vient l'action."""
        return self.evenement or self.visite

    @property
    def en_retard(self) -> bool:
        return self.statut == self.Statut.A_FAIRE and self.echeance < timezone.localdate()

    def peut_agir(self, u) -> bool:
        return self.statut == self.Statut.A_FAIRE and (self.responsable_id == u.id or u.has_perm("hse.traiter_evenement"))

    def terminer(self, utilisateur, commentaire=""):
        if not self.peut_agir(utilisateur):
            raise PermissionDenied("Seul le responsable de l'action ou le responsable HSE la termine, tant qu'elle est à faire.")
        self.statut, self.faite_le, self.commentaire, self.modifie_par = self.Statut.FAITE, timezone.localdate(), (commentaire or "").strip(), utilisateur
        self.save()

    def abandonner(self, utilisateur, commentaire):
        if not utilisateur.has_perm("hse.traiter_evenement"):
            raise PermissionDenied("Seul le responsable HSE abandonne une action.")
        if self.statut != self.Statut.A_FAIRE:
            raise ValidationError("Cette action n'est plus à faire.")
        if not (commentaire or "").strip():
            raise ValidationError("Indiquez pourquoi l'action est abandonnée.")
        self.statut, self.commentaire, self.modifie_par = self.Statut.ABANDONNEE, commentaire.strip(), utilisateur
        self.save()


def indicateurs(annee=None) -> dict:
    """Chiffres de l'année : événements par type, accidents avec arrêt, jours d'arrêt, jours sans accident avec arrêt."""
    aujourd_hui = timezone.localdate()
    annee = annee or aujourd_hui.year
    de_l_annee = Evenement.objects.filter(date__year=annee)
    par_type = {t: 0 for t in Evenement.Type.values}
    for t in de_l_annee.values_list("type", flat=True):
        par_type[t] += 1
    avec_arret = Evenement.objects.filter(type=Evenement.Type.ACCIDENT, jours_arret__gt=0)
    dernier = avec_arret.order_by("-date").first()
    A = ActionCorrective.Statut
    return {
        "annee": annee, "total": sum(par_type.values()),
        "par_type": [{"type": t, "libelle": Evenement.Type(t).label, "nombre": n} for t, n in par_type.items()],
        "accidents_avec_arret": avec_arret.filter(date__year=annee).count(),
        "jours_arret": sum(avec_arret.filter(date__year=annee).values_list("jours_arret", flat=True)),
        "jours_sans_accident": (aujourd_hui - timezone.localtime(dernier.date).date()).days if dernier else None,
        "a_traiter": Evenement.objects.exclude(statut=Evenement.Statut.CLOS).count(),
        "actions_en_retard": ActionCorrective.objects.filter(statut=A.A_FAIRE, echeance__lt=aujourd_hui).count(),
    }


from .terrain import DotationEPI, Visite  # noqa: E402,F401  (modèles déclarés dans terrain.py)
