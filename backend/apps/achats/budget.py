"""Demandes liées au budget : demande d'achat de frais généraux et de sous-traitance (DA), demande
d'investissement non productif ou productif (DI). Le circuit suit les procédures Achats :
service demandeur, accord de la direction générale si besoin, consultation des fournisseurs par les achats,
puis validations du responsable achats, du contrôle de gestion, de la direction financière et,
selon le cas, de la direction générale."""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone

from apps.core.models import Compteur, Horodate, Service, Site, Societe
from apps.referentiels.models import CompteCharge, Projet, Tiers

from .choix import Activite


class LigneBudgetaire(Horodate):
    """Ligne du budget annuel d'un service, tenue par le contrôle de gestion."""

    exercice = models.PositiveIntegerField("exercice (année)")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="lignes_budgetaires")
    intitule = models.CharField("intitulé", max_length=150)
    compte = models.ForeignKey(CompteCharge, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    montant = models.DecimalField("montant du budget", max_digits=14, decimal_places=0)
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = "ligne budgétaire"
        verbose_name_plural = "lignes budgétaires"
        ordering = ["-exercice", "service__nom", "intitule"]
        constraints = [
            models.UniqueConstraint(fields=["exercice", "service", "intitule"], name="ligne_budgetaire_unique"),
            models.CheckConstraint(name="ligne_budgetaire_montant_positif", condition=models.Q(montant__gte=0)),
        ]

    def __str__(self):
        return f"{self.exercice} · {self.service.nom} · {self.intitule}"

    def engage(self, sauf=None) -> Decimal:
        """Total des demandes validées sur cette ligne (sans la demande « sauf », pour calculer son propre impact)."""
        demandes = self.demandes.filter(statut=DemandeBudget.Statut.VALIDEE)
        if sauf is not None:
            demandes = demandes.exclude(pk=sauf.pk)
        return demandes.aggregate(t=Sum("montant"))["t"] or Decimal(0)

    def disponible(self, sauf=None) -> Decimal:
        return self.montant - self.engage(sauf)


class DemandeBudget(Horodate):
    class Type(models.TextChoices):
        FRAIS_GENERAUX = "FG", "Demande d'achat : frais généraux et sous-traitance"
        INVEST_NON_PRODUCTIF = "DI_NP", "Demande d'investissement non productif"
        INVEST_PRODUCTIF = "DI_P", "Demande d'investissement productif"

    class Statut(models.TextChoices):
        BROUILLON = "BROUILLON", "Brouillon"
        ATTENTE_SERVICE = "ATT_SERVICE", "En attente du responsable de service"
        ATTENTE_ACCORD_DG = "ATT_ACCORD", "En attente de l'accord de la direction générale"
        CONSULTATION = "CONSULT", "Consultation des fournisseurs par les achats"
        ATTENTE_ACHATS = "ATT_ACHATS", "En attente du responsable achats"
        ATTENTE_CONTROLE = "ATT_CDG", "En attente du contrôle de gestion"
        ATTENTE_FINANCE = "ATT_RAF", "En attente de la direction financière"
        ATTENTE_DG = "ATT_DG", "En attente de la direction générale"
        VALIDEE = "VALIDEE", "Validée"
        REFUSEE = "REFUSEE", "Refusée"

    class Nature(models.TextChoices):
        # investissement non productif
        CONSTRUCTIONS = "CONSTRUCTIONS", "Constructions"
        INSTALLATIONS_TECHNIQUES = "INSTALL_TECH", "Installations techniques"
        MOBILIER_BUREAU = "MOB_BUREAU", "Matériel et mobilier de bureau"
        OUTILLAGE = "OUTILLAGE", "Matériel et outillage"
        INFORMATIQUE = "INFORMATIQUE", "Matériel informatique"
        MOBILIER_HABITATION = "MOB_HABITAT", "Matériel et mobilier d'habitation"
        AGENCEMENTS = "AGENCEMENTS", "Agencements et installations"
        # investissement productif
        MANUTENTION = "MANUTENTION", "Matériel de manutention"
        LEVAGE = "LEVAGE", "Matériel de levage et grutage"
        # les deux
        TRANSPORT = "TRANSPORT", "Matériel de transport"
        AUTRES = "AUTRES", "Autres"

    NATURES = {
        Type.INVEST_NON_PRODUCTIF: ["CONSTRUCTIONS", "INSTALL_TECH", "MOB_BUREAU", "OUTILLAGE", "INFORMATIQUE",
                                    "MOB_HABITAT", "TRANSPORT", "AGENCEMENTS", "AUTRES"],
        Type.INVEST_PRODUCTIF: ["MANUTENTION", "TRANSPORT", "LEVAGE", "AUTRES"],
    }

    class Motif(models.TextChoices):
        DEVELOPPEMENT = "DEVELOPPEMENT", "Développement"
        RENOUVELLEMENT = "RENOUVELLEMENT", "Renouvellement"

    type = models.CharField(max_length=5, choices=Type.choices)
    numero = models.CharField("n°", max_length=20, unique=True, editable=False)
    ancien_numero = models.CharField("n° dans l'ancien logiciel", max_length=30, blank=True)
    statut = models.CharField(max_length=11, choices=Statut.choices, default=Statut.BROUILLON, editable=False)
    date = models.DateField(default=timezone.localdate)
    fast_track = models.BooleanField("Fast-Track", default=False)

    demandeur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="demandes_budget")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="demandes_budget",
                                verbose_name="service demandeur")
    site = models.ForeignKey(Site, on_delete=models.PROTECT, related_name="demandes_budget")
    activite = models.CharField("activité", max_length=12, choices=Activite.choices, blank=True)
    activite_autre = models.CharField("autre activité", max_length=100, blank=True)
    projet = models.ForeignKey(Projet, null=True, blank=True, on_delete=models.PROTECT, related_name="+",
                               verbose_name="projet / client")
    intitule = models.CharField("intitulé", max_length=150)
    description = models.TextField("description de l'achat", blank=True)

    # Budget, déclaré par le demandeur puis confirmé par le contrôle de gestion
    prevu_budget = models.BooleanField("prévu au budget", default=True)
    ligne_budgetaire = models.ForeignKey(LigneBudgetaire, null=True, blank=True, on_delete=models.PROTECT,
                                         related_name="demandes", verbose_name="ligne budgétaire")
    motif_hors_budget = models.TextField("motif du hors budget", blank=True)

    # Investissement
    nature = models.CharField("nature de l'investissement", max_length=14, choices=Nature.choices, blank=True)
    motif_investissement = models.CharField("motif", max_length=14, choices=Motif.choices, blank=True)
    numero_contrat = models.CharField("n° de contrat", max_length=50, blank=True)
    client = models.ForeignKey(Tiers, null=True, blank=True, on_delete=models.PROTECT, related_name="+",
                               limit_choices_to={"est_client": True})
    loyer_mensuel = models.DecimalField("loyer mensuel", max_digits=14, decimal_places=0, null=True, blank=True)
    duree_amortissement = models.PositiveIntegerField("durée d'amortissement (mois)", null=True, blank=True)

    # Achats : mise en concurrence
    acheteur = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, editable=False,
                                 on_delete=models.PROTECT, related_name="demandes_budget_attribuees")
    critere_qualite = models.BooleanField("critère : qualité", default=False)
    critere_delai = models.BooleanField("critère : délai", default=False)
    critere_prix = models.BooleanField("critère : prix", default=False)
    critere_autre = models.CharField("autres critères", max_length=150, blank=True)
    justification_devis = models.TextField("justification s'il y a moins de trois devis", blank=True)
    montant = models.DecimalField("montant retenu", max_digits=14, decimal_places=0, null=True, blank=True, editable=False)

    # Contrôle de gestion : imputation
    service_impute = models.ForeignKey(Service, null=True, blank=True, on_delete=models.PROTECT, related_name="+",
                                       verbose_name="service imputé")
    compte = models.ForeignKey(CompteCharge, null=True, blank=True, on_delete=models.PROTECT, related_name="+",
                               verbose_name="compte comptable")

    class Meta:
        verbose_name = "demande liée au budget"
        verbose_name_plural = "demandes liées au budget"
        ordering = ["-cree_le"]
        permissions = [
            ("voir_toutes_demandebudget", "Peut voir toutes les demandes liées au budget"),
            ("traiter_demandebudget", "Peut consulter les fournisseurs (acheteur)"),
            ("valider_achats_demandebudget", "Peut valider pour les achats"),
            ("valider_controle_demandebudget", "Peut imputer et valider pour le contrôle de gestion"),
            ("valider_finance_demandebudget", "Peut valider pour la direction financière"),
            ("valider_dg_demandebudget", "Peut valider pour la direction générale"),
        ]

    def __str__(self):
        return self.numero

    def save(self, *args, **kwargs):
        if not self.numero:
            with transaction.atomic():
                prefixe = "DAB" if self.type == self.Type.FRAIS_GENERAUX else "DI"
                annee = self.date.year
                self.numero = f"{prefixe}-{annee}-{Compteur.suivant(f'{prefixe}-{annee}'):04d}"
                return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)

    # ----- lecture

    @property
    def est_investissement(self) -> bool:
        return self.type != self.Type.FRAIS_GENERAUX

    @property
    def modifiable(self) -> bool:
        return self.statut == self.Statut.BROUILLON

    @property
    def activite_libelle(self) -> str:
        if self.activite == Activite.AUTRE and self.activite_autre:
            return self.activite_autre
        return self.get_activite_display()

    @property
    def devis_retenu(self):
        return next((d for d in self.devis.all() if d.retenu), None)

    @property
    def accord_dg_requis(self) -> bool:
        """Avant de consulter les fournisseurs : toute demande d'investissement, et tout achat hors budget."""
        return self.est_investissement or not self.prevu_budget

    def situation_budget(self):
        """Budget, déjà engagé, disponible, à engager et solde de la ligne, sans compter cette demande."""
        ligne = self.ligne_budgetaire
        if not ligne:
            return None
        engage = ligne.engage(sauf=self)
        a_engager = self.montant or Decimal(0)
        return {"budget": ligne.montant, "engage": engage, "disponible": ligne.montant - engage,
                "a_engager": a_engager, "solde": ligne.montant - engage - a_engager}

    @property
    def depasse_budget(self) -> bool:
        situation = self.situation_budget()
        return bool(situation and situation["solde"] < 0)

    def motifs_dg(self) -> list:
        """Raisons pour lesquelles la direction générale doit valider en dernier."""
        motifs = []
        seuil = Societe.courante().seuil_validation_dg
        if self.est_investissement:
            motifs.append("demande d'investissement")
        if (self.montant or 0) > seuil:
            motifs.append(f"montant supérieur à {seuil:,.0f} francs CFA".replace(",", " "))
        if not self.prevu_budget:
            motifs.append("achat hors budget")
        if self.depasse_budget:
            motifs.append("dépassement de la ligne budgétaire")
        return motifs

    # ----- droits

    def peut_valider(self, utilisateur) -> bool:
        """Vrai si l'utilisateur est le valideur attendu à l'étape en cours."""
        S = self.Statut
        droits = {
            S.ATTENTE_ACCORD_DG: "valider_dg", S.ATTENTE_ACHATS: "valider_achats", S.ATTENTE_CONTROLE: "valider_controle",
            S.ATTENTE_FINANCE: "valider_finance", S.ATTENTE_DG: "valider_dg",
        }
        if self.statut == S.ATTENTE_SERVICE:
            return self.service.responsable_id == utilisateur.id
        if self.statut in droits:
            return utilisateur.has_perm(f"achats.{droits[self.statut]}_demandebudget")
        return False

    def peut_consulter(self, utilisateur) -> bool:
        """L'acheteur chargé de la demande ou le responsable achats, pendant la consultation des fournisseurs."""
        return self.statut == self.Statut.CONSULTATION and (
            self.acheteur_id == utilisateur.id or utilisateur.has_perm("achats.valider_achats_demandebudget")
        )

    def peut_imputer(self, utilisateur) -> bool:
        return self.statut == self.Statut.ATTENTE_CONTROLE and utilisateur.has_perm("achats.valider_controle_demandebudget")

    def peut_voir(self, utilisateur) -> bool:
        return (utilisateur.has_perm("achats.voir_toutes_demandebudget") or self.demandeur_id == utilisateur.id
                or self.service.responsable_id == utilisateur.id)

    # ----- circuit

    def _journal(self, utilisateur, action, commentaire=""):
        self.evenements.create(auteur=utilisateur, action=action, statut=self.statut, commentaire=commentaire)

    def _controler_fiche(self):
        erreurs = []
        if not self.service.responsable_id:
            erreurs.append(f"Le service {self.service} n'a pas de responsable désigné pour valider la demande.")
        if not self.prevu_budget and not self.motif_hors_budget.strip():
            erreurs.append("Indiquez le motif du hors budget.")
        if self.est_investissement and not self.nature:
            erreurs.append("Indiquez la nature de l'investissement.")
        if self.nature and self.est_investissement and self.nature not in self.NATURES[self.type]:
            erreurs.append("Cette nature ne correspond pas au type d'investissement.")
        if self.type == self.Type.INVEST_PRODUCTIF and not self.motif_investissement:
            erreurs.append("Précisez s'il s'agit d'un développement ou d'un renouvellement.")
        if erreurs:
            raise ValidationError(erreurs)

    def _controler_consultation(self):
        devis = list(self.devis.all())
        retenus = [d for d in devis if d.retenu]
        erreurs = []
        if len(retenus) != 1:
            erreurs.append("Désignez le devis retenu (un seul).")
        if not self.est_investissement and len(devis) < 3 and not self.justification_devis.strip():
            erreurs.append("Trois devis sont attendus : ajoutez-les ou justifiez leur absence.")
        if erreurs:
            raise ValidationError(erreurs)
        self.montant = retenus[0].montant

    def _controler_imputation(self):
        erreurs = []
        if not self.service_impute_id:
            erreurs.append("Indiquez le service imputé.")
        if not self.compte_id:
            erreurs.append("Indiquez le compte comptable.")
        if self.prevu_budget and not self.ligne_budgetaire_id:
            erreurs.append("Indiquez la ligne budgétaire, ou déclarez l'achat hors budget.")
        if erreurs:
            raise ValidationError(erreurs)

    def _attribuer(self):
        from .models import Acheteur

        deja = Acheteur.objects.filter(utilisateur_id=self.acheteur_id, disponible=True, utilisateur__is_active=True)
        if not deja.exists():  # une demande représentée revient au même acheteur s'il est disponible
            choisi = Acheteur.choisir()
            self.acheteur = choisi.utilisateur if choisi else None

    @transaction.atomic
    def soumettre(self, utilisateur):
        if not self.modifiable:
            raise ValidationError("Cette demande a déjà été soumise.")
        if utilisateur.id != self.demandeur_id:
            raise PermissionDenied("Seul le demandeur peut soumettre sa demande.")
        self._controler_fiche()
        self.statut = self.Statut.ATTENTE_SERVICE
        self.save()
        self._journal(utilisateur, EvenementBudget.Action.SOUMISSION)

    @transaction.atomic
    def proposer(self, utilisateur):
        """Fin de la consultation : les achats proposent le fournisseur retenu aux valideurs."""
        if not self.peut_consulter(utilisateur):
            raise PermissionDenied("Seul l'acheteur chargé de la demande ou le responsable achats peut la proposer.")
        self._controler_consultation()
        self.statut = self.Statut.ATTENTE_ACHATS
        self.save()
        self._journal(utilisateur, EvenementBudget.Action.PROPOSITION, f"{self.devis_retenu.fournisseur} retenu")

    @transaction.atomic
    def valider(self, utilisateur, commentaire=""):
        if not self.peut_valider(utilisateur):
            raise PermissionDenied("Vous n'êtes pas le valideur attendu à cette étape.")
        S = self.Statut
        if self.statut == S.ATTENTE_SERVICE:
            suivant = S.ATTENTE_ACCORD_DG if self.accord_dg_requis else S.CONSULTATION
        elif self.statut == S.ATTENTE_ACCORD_DG:
            suivant = S.CONSULTATION
        elif self.statut == S.ATTENTE_ACHATS:
            self._controler_consultation()
            suivant = S.ATTENTE_CONTROLE
        elif self.statut == S.ATTENTE_CONTROLE:
            self._controler_imputation()
            suivant = S.ATTENTE_FINANCE
        elif self.statut == S.ATTENTE_FINANCE:
            suivant = S.ATTENTE_DG if self.motifs_dg() else S.VALIDEE
        else:
            suivant = S.VALIDEE
        action = EvenementBudget.Action.ACCORD if self.statut == S.ATTENTE_ACCORD_DG else EvenementBudget.Action.VALIDATION
        etape = self.statut
        if suivant == S.CONSULTATION:
            self._attribuer()
        self.statut = suivant
        self.save()
        self.evenements.create(auteur=utilisateur, action=action, statut=self.statut, etape=etape, commentaire=commentaire)

    @transaction.atomic
    def refuser(self, utilisateur, commentaire):
        if not self.peut_valider(utilisateur):
            raise PermissionDenied("Vous n'êtes pas le valideur attendu à cette étape.")
        if not commentaire.strip():
            raise ValidationError("Indiquez le motif du refus.")
        self.statut = self.Statut.REFUSEE
        self.save()
        self._journal(utilisateur, EvenementBudget.Action.REFUS, commentaire)

    @transaction.atomic
    def renvoyer(self, utilisateur, commentaire):
        """« À représenter » : la demande retourne au demandeur, puis repasse par tout le circuit."""
        if not (self.peut_valider(utilisateur) or self.peut_consulter(utilisateur)):
            raise PermissionDenied("Vous ne pouvez pas renvoyer cette demande à cette étape.")
        if not commentaire.strip():
            raise ValidationError("Indiquez ce qui doit être corrigé.")
        self.statut = self.Statut.BROUILLON
        self.save()
        self._journal(utilisateur, EvenementBudget.Action.RENVOI, commentaire)

    def signatures(self) -> list:
        """Dernière validation de chaque étape du circuit en cours, dans l'ordre : (libellé, événement ou None)."""
        S = self.Statut
        etapes = [(S.ATTENTE_SERVICE, "Responsable du service"), (S.ATTENTE_ACHATS, "Responsable achats"),
                  (S.ATTENTE_CONTROLE, "Contrôle de gestion"), (S.ATTENTE_FINANCE, "Direction financière")]
        if self.statut == S.ATTENTE_DG or self.motifs_dg():
            etapes.append((S.ATTENTE_DG, "Direction générale"))
        evenements = list(self.evenements.all())
        # seules comptent les validations postérieures au dernier renvoi au demandeur
        for i in range(len(evenements) - 1, -1, -1):
            if evenements[i].action == EvenementBudget.Action.RENVOI:
                evenements = evenements[i + 1:]
                break
        par_etape = {e.etape: e for e in evenements if e.action == EvenementBudget.Action.VALIDATION}
        return [(libelle, par_etape.get(etape)) for etape, libelle in etapes]


class DevisDemande(models.Model):
    """Devis reçu d'un fournisseur pendant la consultation."""

    demande = models.ForeignKey(DemandeBudget, on_delete=models.CASCADE, related_name="devis")
    fournisseur = models.ForeignKey(Tiers, on_delete=models.PROTECT, related_name="+",
                                    limit_choices_to={"est_fournisseur": True})
    numero = models.CharField("n° de devis", max_length=50, blank=True)
    date = models.DateField(null=True, blank=True)
    montant = models.DecimalField(max_digits=14, decimal_places=0)
    retenu = models.BooleanField(default=False)

    class Meta:
        verbose_name = "devis"
        verbose_name_plural = "devis"
        ordering = ["id"]
        constraints = [models.CheckConstraint(name="devis_demande_montant_positif", condition=models.Q(montant__gt=0))]


class EvenementBudget(models.Model):
    """Journal de la demande : qui a fait quoi, à quelle étape et quand."""

    class Action(models.TextChoices):
        SOUMISSION = "SOUMISSION", "Soumission"
        ACCORD = "ACCORD", "Accord de principe"
        PROPOSITION = "PROPOSITION", "Fournisseur proposé"
        VALIDATION = "VALIDATION", "Validation"
        REFUS = "REFUS", "Refus"
        RENVOI = "RENVOI", "À représenter"

    demande = models.ForeignKey(DemandeBudget, on_delete=models.CASCADE, related_name="evenements")
    action = models.CharField(max_length=12, choices=Action.choices)
    etape = models.CharField("étape validée", max_length=11, choices=DemandeBudget.Statut.choices, blank=True)
    statut = models.CharField("statut obtenu", max_length=11, choices=DemandeBudget.Statut.choices)
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    date = models.DateTimeField(auto_now_add=True)
    commentaire = models.TextField(blank=True)

    class Meta:
        verbose_name = "événement de demande liée au budget"
        ordering = ["id"]
