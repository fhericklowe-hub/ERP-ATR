"""Ressources humaines : le dossier de chaque salarié, ses contrats, et ses pièces à échéance (permis, autorisation
de conduite d'engins, visite médicale, pièce d'identité). Ces données sont confidentielles : seuls les rôles RH y
ont accès. La paie n'est pas traitée ici."""
import datetime

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.core.models import Compteur, Horodate, Service, Site


class Salarie(Horodate):
    class Statut(models.TextChoices):
        ACTIF = "ACTIF", "En poste"
        SORTI = "SORTI", "Sorti des effectifs"

    class Sexe(models.TextChoices):
        HOMME = "M", "Homme"
        FEMME = "F", "Femme"

    class Categorie(models.TextChoices):
        CADRE = "CADRE", "Cadre"
        MAITRISE = "MAITRISE", "Agent de maîtrise"
        EMPLOYE = "EMPLOYE", "Employé"
        OUVRIER = "OUVRIER", "Ouvrier"

    class Situation(models.TextChoices):
        CELIBATAIRE = "CELIB", "Célibataire"
        MARIE = "MARIE", "Marié(e)"
        DIVORCE = "DIVORCE", "Divorcé(e)"
        VEUF = "VEUF", "Veuf ou veuve"

    matricule = models.CharField(max_length=20, unique=True, blank=True,
                                 help_text="Laissez vide pour un matricule automatique.")
    statut = models.CharField(max_length=5, choices=Statut.choices, default=Statut.ACTIF, editable=False)
    nom = models.CharField(max_length=80)
    prenoms = models.CharField("prénoms", max_length=120)
    sexe = models.CharField(max_length=1, choices=Sexe.choices, blank=True)
    date_naissance = models.DateField("date de naissance", null=True, blank=True)
    lieu_naissance = models.CharField("lieu de naissance", max_length=100, blank=True)
    nationalite = models.CharField("nationalité", max_length=60, blank=True)
    situation_familiale = models.CharField(max_length=7, choices=Situation.choices, blank=True)
    enfants = models.PositiveSmallIntegerField("enfants à charge", default=0)
    telephone = models.CharField("téléphone", max_length=30, blank=True)
    email = models.EmailField("e-mail", blank=True)
    adresse = models.CharField(max_length=200, blank=True)
    contact_urgence = models.CharField("personne à prévenir", max_length=120, blank=True)
    telephone_urgence = models.CharField("téléphone de la personne à prévenir", max_length=30, blank=True)
    numero_cnps = models.CharField("n° CNPS", max_length=30, blank=True)

    site = models.ForeignKey(Site, on_delete=models.PROTECT, related_name="salaries")
    service = models.ForeignKey(Service, null=True, blank=True, on_delete=models.PROTECT, related_name="salaries")
    fonction = models.CharField(max_length=100, blank=True)
    categorie = models.CharField("catégorie", max_length=8, choices=Categorie.choices, blank=True)
    responsable = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="equipe",
                                    verbose_name="responsable hiérarchique")
    utilisateur = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                       related_name="salarie", verbose_name="compte dans l'ERP")
    date_embauche = models.DateField("date d'embauche", null=True, blank=True)
    date_sortie = models.DateField("date de sortie", null=True, blank=True, editable=False)
    motif_sortie = models.CharField("motif de la sortie", max_length=200, blank=True, editable=False)
    observations = models.TextField(blank=True)

    class Meta:
        verbose_name = "salarié"
        ordering = ["nom", "prenoms"]
        permissions = [("gerer_sortie_salarie", "Peut enregistrer la sortie ou le retour d'un salarié")]

    def __str__(self):
        return f"{self.nom} {self.prenoms}".strip()

    @transaction.atomic
    def save(self, *args, **kwargs):
        self.nom, self.prenoms = self.nom.strip().upper(), self.prenoms.strip()
        if not self.matricule:
            self.matricule = f"S{Compteur.suivant('SALARIE'):04d}"
            while Salarie.objects.filter(matricule=self.matricule).exists():
                self.matricule = f"S{Compteur.suivant('SALARIE'):04d}"
        super().save(*args, **kwargs)

    def clean(self):
        aujourd_hui = timezone.localdate()
        if self.date_naissance and self.date_naissance > aujourd_hui:
            raise ValidationError({"date_naissance": "La date de naissance est dans le futur."})
        if self.date_naissance and self.date_embauche and self.date_embauche <= self.date_naissance:
            raise ValidationError({"date_embauche": "L'embauche ne peut pas précéder la naissance."})
        if self.responsable_id and self.responsable_id == self.id:
            raise ValidationError({"responsable": "Un salarié n'est pas son propre responsable."})

    @property
    def anciennete(self):
        """Années entières depuis l'embauche, jusqu'à la sortie ou aujourd'hui."""
        if not self.date_embauche:
            return None
        fin = self.date_sortie or timezone.localdate()
        return max(0, fin.year - self.date_embauche.year - ((fin.month, fin.day) < (self.date_embauche.month, self.date_embauche.day)))

    @property
    def contrat_en_cours(self):
        aujourd_hui = timezone.localdate()
        for c in sorted(self.contrats.all(), key=lambda c: c.date_debut, reverse=True):
            if c.date_debut <= aujourd_hui and (c.date_fin is None or c.date_fin >= aujourd_hui):
                return c
        return None

    def _exiger(self, utilisateur):
        if not utilisateur.has_perm("rh.gerer_sortie_salarie"):
            raise PermissionDenied("Seul le gestionnaire RH enregistre une sortie des effectifs.")

    def sortir(self, utilisateur, date_sortie, motif):
        self._exiger(utilisateur)
        if self.statut != self.Statut.ACTIF:
            raise ValidationError("Ce salarié est déjà sorti des effectifs.")
        if not date_sortie:
            raise ValidationError("Indiquez la date de sortie.")
        if self.date_embauche and date_sortie < self.date_embauche:
            raise ValidationError("La sortie ne peut pas précéder l'embauche.")
        if not (motif or "").strip():
            raise ValidationError("Indiquez le motif (démission, fin de contrat, licenciement, retraite...).")
        self.statut, self.date_sortie, self.motif_sortie, self.modifie_par = self.Statut.SORTI, date_sortie, motif.strip()[:200], utilisateur
        self.save()

    def reintegrer(self, utilisateur):
        """Sortie saisie par erreur, ou retour dans l'entreprise."""
        self._exiger(utilisateur)
        if self.statut != self.Statut.SORTI:
            raise ValidationError("Ce salarié est en poste.")
        self.statut, self.date_sortie, self.motif_sortie, self.modifie_par = self.Statut.ACTIF, None, "", utilisateur
        self.save()


class Contrat(Horodate):
    class Type(models.TextChoices):
        CDI = "CDI", "CDI"
        CDD = "CDD", "CDD"
        STAGE = "STAGE", "Stage"
        JOURNALIER = "JOURNALIER", "Journalier"
        PRESTATAIRE = "PRESTA", "Prestataire ou intérimaire"

    salarie = models.ForeignKey(Salarie, on_delete=models.CASCADE, related_name="contrats")
    type = models.CharField(max_length=10, choices=Type.choices)
    date_debut = models.DateField("début")
    date_fin = models.DateField("fin", null=True, blank=True, help_text="Vide pour un contrat sans terme.")
    fin_essai = models.DateField("fin de la période d'essai", null=True, blank=True)
    fonction = models.CharField(max_length=100, blank=True)
    observations = models.TextField(blank=True)

    class Meta:
        verbose_name = "contrat de travail"
        verbose_name_plural = "contrats de travail"
        ordering = ["-date_debut"]

    def __str__(self):
        return f"{self.get_type_display()} du {self.date_debut:%d/%m/%Y}"

    def clean(self):
        if self.date_fin and self.date_fin < self.date_debut:
            raise ValidationError({"date_fin": "La fin ne peut pas précéder le début."})
        if self.fin_essai and (self.fin_essai < self.date_debut or (self.date_fin and self.fin_essai > self.date_fin)):
            raise ValidationError({"fin_essai": "La période d'essai doit se terminer pendant le contrat."})
        if self.type in (self.Type.CDD, self.Type.STAGE) and not self.date_fin:
            raise ValidationError({"date_fin": "Un CDD ou un stage a une date de fin."})


class PieceSalarie(Horodate):
    """Pièce du dossier qui a une validité : à son approche, le gestionnaire RH est prévenu."""

    class Type(models.TextChoices):
        IDENTITE = "IDENTITE", "Pièce d'identité"
        SEJOUR = "SEJOUR", "Carte de séjour"
        PERMIS = "PERMIS", "Permis de conduire"
        CONDUITE = "CONDUITE", "Autorisation de conduite d'engins"
        HABILITATION = "HABILIT", "Habilitation ou certificat"
        MEDICALE = "MEDICALE", "Visite médicale"
        DIPLOME = "DIPLOME", "Diplôme"
        AUTRE = "AUTRE", "Autre"

    salarie = models.ForeignKey(Salarie, on_delete=models.CASCADE, related_name="pieces")
    type = models.CharField(max_length=8, choices=Type.choices)
    libelle = models.CharField("précision", max_length=120, blank=True, help_text="Catégorie du permis, type d'engin, organisme...")
    numero = models.CharField("numéro", max_length=60, blank=True)
    date_delivrance = models.DateField("délivré le", null=True, blank=True)
    date_expiration = models.DateField("valable jusqu'au", null=True, blank=True)

    class Meta:
        verbose_name = "pièce du dossier"
        verbose_name_plural = "pièces du dossier"
        ordering = ["date_expiration", "id"]

    def __str__(self):
        return " ".join(filter(None, [self.get_type_display(), self.libelle]))

    def clean(self):
        if self.date_delivrance and self.date_expiration and self.date_expiration < self.date_delivrance:
            raise ValidationError({"date_expiration": "La validité ne peut pas se terminer avant la délivrance."})


RAPPEL_JOURS = 30


def echeances(jours=RAPPEL_JOURS, salaries=None) -> list:
    """Ce qui arrive à terme pour les salariés en poste : pièces à renouveler, fins de contrat, fins de période d'essai.
    Liste de dicts triée par date ; une pièce déjà remplacée par une plus récente du même type n'est pas signalée."""
    aujourd_hui = timezone.localdate()
    limite = aujourd_hui + datetime.timedelta(days=jours)
    actifs = Salarie.objects.filter(statut=Salarie.Statut.ACTIF) if salaries is None else salaries
    lignes = []

    def ajouter(salarie, genre, libelle, date, objet):
        lignes.append({"salarie": salarie.id, "salarie_nom": str(salarie), "matricule": salarie.matricule, "genre": genre,
                       "libelle": libelle, "date": date, "jours": (date - aujourd_hui).days, "objet": objet})

    dernieres = {}
    for p in PieceSalarie.objects.filter(salarie__in=actifs).exclude(date_expiration=None).select_related("salarie"):
        cle = (p.salarie_id, p.type, p.libelle.strip().lower())
        if cle not in dernieres or p.date_expiration > dernieres[cle].date_expiration:
            dernieres[cle] = p
    for p in dernieres.values():
        if p.date_expiration <= limite:
            ajouter(p.salarie, "PIECE", str(p), p.date_expiration, p.id)
    contrats = Contrat.objects.filter(salarie__in=actifs).select_related("salarie")
    for c in contrats.filter(date_fin__gte=aujourd_hui, date_fin__lte=limite):
        if not Contrat.objects.filter(salarie=c.salarie, date_debut__gt=c.date_debut).exists():   # pas encore renouvelé
            ajouter(c.salarie, "CONTRAT", f"Fin du {c.get_type_display()}", c.date_fin, c.id)
    for c in contrats.filter(fin_essai__gte=aujourd_hui, fin_essai__lte=limite):
        ajouter(c.salarie, "ESSAI", "Fin de la période d'essai", c.fin_essai, c.id)
    return sorted(lignes, key=lambda l: (l["date"], l["salarie_nom"]))
