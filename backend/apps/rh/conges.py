"""Congés et absences : la demande du salarié, validée par son responsable puis par les RH, et le solde de congés.

Les jours se comptent en jours ouvrables (du lundi au samedi). Les droits à congé s'acquièrent par mois de service,
au taux réglé dans l'administration (2,2 jours ouvrables par mois par défaut)."""
import datetime
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone

from apps.core.models import Compteur, Horodate

from .models import Salarie

ZERO = Decimal(0)


class ReglageRH(models.Model):
    """Une seule ligne."""

    conges_par_mois = models.DecimalField("jours de congé acquis par mois", max_digits=4, decimal_places=2, default=Decimal("2.2"),
                                          help_text="En jours ouvrables (du lundi au samedi).")

    class Meta:
        verbose_name = "réglages RH"
        verbose_name_plural = "réglages RH"

    def __str__(self):
        return "Réglages RH"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def courant(cls):
        return cls.objects.filter(pk=1).first() or cls()


def jours_ouvrables(debut: datetime.date, fin: datetime.date) -> int:
    """Jours du lundi au samedi entre deux dates incluses. Les jours fériés ne sont pas déduits."""
    jours, semaines = (fin - debut).days + 1, 0
    if jours <= 0:
        return 0
    semaines, reste = divmod(jours, 7)
    dimanches = semaines + sum(1 for i in range(reste) if (debut + datetime.timedelta(days=i)).weekday() == 6)
    return jours - dimanches


def mois_entiers(debut: datetime.date, fin: datetime.date) -> int:
    if fin < debut:
        return 0
    return (fin.year - debut.year) * 12 + fin.month - debut.month - (fin.day < debut.day)


class DemandeAbsence(Horodate):
    class Type(models.TextChoices):
        CONGE = "CONGE", "Congé annuel"
        PERMISSION = "PERMISSION", "Permission exceptionnelle"
        MALADIE = "MALADIE", "Maladie"
        MATERNITE = "MATERNITE", "Maternité ou paternité"
        SANS_SOLDE = "SANS_SOLDE", "Absence sans solde"
        AUTRE = "AUTRE", "Autre absence"

    class Statut(models.TextChoices):
        SOUMISE = "SOUMISE", "En attente du responsable"
        VISEE = "VISEE", "En attente des RH"
        APPROUVEE = "APPROUVEE", "Approuvée"
        REFUSEE = "REFUSEE", "Refusée"
        ANNULEE = "ANNULEE", "Annulée"

    numero = models.CharField("n°", max_length=20, unique=True, editable=False)
    statut = models.CharField(max_length=9, choices=Statut.choices, default=Statut.SOUMISE, editable=False)
    salarie = models.ForeignKey(Salarie, on_delete=models.PROTECT, related_name="absences", verbose_name="salarié")
    type = models.CharField(max_length=10, choices=Type.choices, default=Type.CONGE)
    date_debut = models.DateField("du")
    date_fin = models.DateField("au")
    jours = models.DecimalField("jours ouvrables", max_digits=5, decimal_places=1, editable=False)
    motif = models.CharField(max_length=200, blank=True)
    vise_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, editable=False, on_delete=models.PROTECT, related_name="+")
    vise_le = models.DateTimeField(null=True, blank=True, editable=False)
    approuve_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, editable=False, on_delete=models.PROTECT, related_name="+")
    approuve_le = models.DateTimeField(null=True, blank=True, editable=False)
    commentaire = models.TextField("motif du refus ou de l'annulation", blank=True, editable=False)

    class Meta:
        verbose_name = "demande d'absence"
        verbose_name_plural = "demandes d'absence"
        ordering = ["-date_debut", "-id"]
        permissions = [("approuver_demandeabsence", "Peut approuver les absences pour les RH et voir toutes les demandes")]

    def __str__(self):
        return self.numero

    def clean(self):
        if self.date_fin < self.date_debut:
            raise ValidationError({"date_fin": "La fin ne peut pas précéder le début."})
        if (self.date_fin - self.date_debut).days > 366:
            raise ValidationError({"date_fin": "Une absence ne dépasse pas un an."})
        if jours_ouvrables(self.date_debut, self.date_fin) == 0:
            raise ValidationError({"date_debut": "Cette période ne contient aucun jour ouvrable."})
        if self.salarie.statut != Salarie.Statut.ACTIF:
            raise ValidationError({"salarie": "Ce salarié est sorti des effectifs."})
        S = self.Statut
        autre = DemandeAbsence.objects.filter(salarie=self.salarie, date_debut__lte=self.date_fin, date_fin__gte=self.date_debut,
                                              statut__in=[S.SOUMISE, S.VISEE, S.APPROUVEE]).exclude(pk=self.pk).first()
        if autre:
            raise ValidationError(f"Cette période chevauche la demande {autre.numero} (du {autre.date_debut:%d/%m/%Y} au {autre.date_fin:%d/%m/%Y}).")

    @transaction.atomic
    def save(self, *args, **kwargs):
        self.jours = jours_ouvrables(self.date_debut, self.date_fin)
        if not self.numero:
            annee = timezone.localdate().year
            self.numero = f"ABS-{annee}-{Compteur.suivant(f'ABS-{annee}'):04d}"
            if not responsable_de(self.salarie):     # personne pour viser : la demande va directement aux RH
                self.statut = self.Statut.VISEE
        super().save(*args, **kwargs)

    # ----- qui peut quoi

    def est_demandeur(self, u) -> bool:
        return self.salarie.utilisateur_id == u.id

    def est_responsable(self, u) -> bool:
        return responsable_de(self.salarie) == u

    def peut_viser(self, u) -> bool:
        return self.statut == self.Statut.SOUMISE and (self.est_responsable(u) or u.has_perm("rh.approuver_demandeabsence"))

    def peut_approuver(self, u) -> bool:
        return self.statut == self.Statut.VISEE and u.has_perm("rh.approuver_demandeabsence")

    def peut_annuler(self, u) -> bool:
        S = self.Statut
        if u.has_perm("rh.approuver_demandeabsence"):
            return self.statut in (S.SOUMISE, S.VISEE, S.APPROUVEE)
        return self.est_demandeur(u) and self.statut in (S.SOUMISE, S.VISEE)

    # ----- circuit

    def viser(self, utilisateur):
        """Accord du responsable hiérarchique."""
        if not self.peut_viser(utilisateur):
            raise PermissionDenied("Seul le responsable du salarié donne cet accord, sur une demande en attente.")
        self.statut, self.vise_par, self.vise_le, self.modifie_par = self.Statut.VISEE, utilisateur, timezone.now(), utilisateur
        self.save()

    def approuver(self, utilisateur):
        if not utilisateur.has_perm("rh.approuver_demandeabsence"):
            raise PermissionDenied("Seules les RH approuvent une absence.")
        if self.statut != self.Statut.VISEE:
            raise ValidationError("Cette demande n'attend pas l'accord des RH.")
        if self.type == self.Type.CONGE:
            solde = solde_conges(self.salarie)["solde"]
            if self.jours > solde:
                raise ValidationError(f"Solde de congés insuffisant : {self.jours:n} jours demandés pour {solde:n} disponibles. "
                                      "Réduisez la période ou choisissez une absence sans solde.")
        self.statut, self.approuve_par, self.approuve_le, self.modifie_par = self.Statut.APPROUVEE, utilisateur, timezone.now(), utilisateur
        self.save()

    def refuser(self, utilisateur, commentaire):
        if not (self.peut_viser(utilisateur) or self.peut_approuver(utilisateur)):
            raise PermissionDenied("Vous ne pouvez pas refuser cette demande.")
        self._fermer(utilisateur, self.Statut.REFUSEE, commentaire)

    def annuler(self, utilisateur, commentaire=""):
        if not self.peut_annuler(utilisateur):
            raise PermissionDenied("Vous ne pouvez pas annuler cette demande.")
        if self.statut == self.Statut.APPROUVEE and not (commentaire or "").strip():
            raise ValidationError("Indiquez le motif de l'annulation.")
        self._fermer(utilisateur, self.Statut.ANNULEE, commentaire or "Annulée par le demandeur", exiger=False)

    def _fermer(self, utilisateur, statut, commentaire, exiger=True):
        if exiger and not (commentaire or "").strip():
            raise ValidationError("Indiquez le motif.")
        self.statut, self.commentaire, self.modifie_par = statut, (commentaire or "").strip(), utilisateur
        self.save()


def responsable_de(salarie):
    """Le compte qui vise les absences : le responsable hiérarchique, sinon le responsable du service. Jamais soi-même."""
    candidats = [salarie.responsable.utilisateur if salarie.responsable_id else None,
                 salarie.service.responsable if salarie.service_id else None]
    for compte in candidats:
        if compte and compte.is_active and compte.id != salarie.utilisateur_id:
            return compte
    return None


def solde_conges(salarie, au: datetime.date | None = None) -> dict:
    """Droits acquis depuis le point de départ (date du solde repris, sinon l'embauche), congés pris, solde."""
    au = au or timezone.localdate()
    depuis = salarie.conges_depuis or salarie.date_embauche
    fin = min(au, salarie.date_sortie) if salarie.date_sortie else au
    acquis = ZERO if not depuis else (mois_entiers(depuis, fin) * ReglageRH.courant().conges_par_mois)
    S, T = DemandeAbsence.Statut, DemandeAbsence.Type
    pris = salarie.absences.filter(type=T.CONGE, statut=S.APPROUVEE)
    if depuis:
        pris = pris.filter(date_debut__gte=depuis)
    pris = pris.aggregate(j=Sum("jours"))["j"] or ZERO
    en_attente = salarie.absences.filter(type=T.CONGE, statut__in=[S.SOUMISE, S.VISEE]).aggregate(j=Sum("jours"))["j"] or ZERO
    return {"depuis": depuis, "repris": salarie.conges_solde_depart, "acquis": acquis, "pris": pris, "en_attente": en_attente,
            "solde": salarie.conges_solde_depart + acquis - pris}
