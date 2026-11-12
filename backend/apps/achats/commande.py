"""Bon de commande fournisseur : créé à partir d'une demande d'achat validée, validé par le responsable
achats puis par le contrôleur de gestion, puis imprimé, signé et transmis au fournisseur."""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.core import devises
from apps.core.devises import arrondi
from apps.core.lettres import montant_en_lettres
from apps.core.models import Compteur, Horodate, Service, Site
from apps.referentiels.models import Article, Tiers

from .choix import Activite

CENT = Decimal(100)


class BonCommande(Horodate):
    class Statut(models.TextChoices):
        BROUILLON = "BROUILLON", "Brouillon"
        ATTENTE_RESPONSABLE = "ATT_RESP", "En attente du responsable achats"
        ATTENTE_CONTROLE = "ATT_CDG", "En attente du contrôleur de gestion"
        VALIDE = "VALIDE", "Validé, à signer et transmettre"
        TRANSMIS = "TRANSMIS", "Transmis au fournisseur"
        CLOTURE = "CLOTURE", "Clôturé"
        ANNULE = "ANNULE", "Annulé"

    class Reglement(models.TextChoices):
        CHEQUE = "CHEQUE", "Chèque"
        VIREMENT = "VIREMENT", "Virement"
        ESPECES = "ESPECES", "Espèces"
        TRAITE = "TRAITE", "Traite"

    numero = models.CharField("n° BC", max_length=20, unique=True, editable=False)
    ancien_numero = models.CharField("n° dans l'ancien logiciel", max_length=30, blank=True)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.BROUILLON, editable=False)
    date = models.DateField(default=timezone.localdate)

    demande = models.ForeignKey(
        "achats.DemandeAchat", on_delete=models.PROTECT, related_name="bons_commande", verbose_name="demande d'achat"
    )
    fournisseur = models.ForeignKey(
        Tiers, on_delete=models.PROTECT, related_name="bons_commande", limit_choices_to={"est_fournisseur": True}
    )
    reference_fournisseur = models.CharField("n° de devis / commande fournisseur", max_length=50, blank=True)
    objet = models.CharField("référence / objet", max_length=150, blank=True)
    site = models.ForeignKey(Site, on_delete=models.PROTECT, related_name="bons_commande", verbose_name="succursale")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="bons_commande", verbose_name="service imputé")
    activite = models.CharField("activité", max_length=12, choices=Activite.choices, blank=True)
    activite_autre = models.CharField("autre activité", max_length=100, blank=True)
    acheteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bons_commande")
    date_livraison = models.DateField("délai de livraison", null=True, blank=True)
    transport = models.CharField(max_length=100, blank=True, default="PAR VOS SOINS")
    adresse_livraison = models.TextField("adresse de livraison", blank=True)
    echeance = models.CharField("échéance de paiement", max_length=100, blank=True, default="30 JOURS FIN DE MOIS")
    mode_reglement = models.CharField("mode de règlement", max_length=10, choices=Reglement.choices, default=Reglement.CHEQUE)
    devise = models.CharField(max_length=3, choices=devises.CHOIX, default="XOF")
    taux_change = models.DecimalField(
        "cours de la devise en francs CFA", max_digits=12, decimal_places=4, null=True, blank=True,
        help_text="Valeur d'une unité de la devise en francs CFA, pour la contre-valeur de la commande.",
    )
    transmis_le = models.DateField("transmis au fournisseur le", null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "bon de commande"
        verbose_name_plural = "bons de commande"
        ordering = ["-cree_le"]
        permissions = [
            ("valider_responsable_boncommande", "Peut valider les bons de commande (responsable achats)"),
            ("valider_controle_boncommande", "Peut valider les bons de commande (contrôle de gestion)"),
        ]

    def __str__(self):
        return self.numero

    def save(self, *args, **kwargs):
        if self.devise == "XOF":
            self.taux_change = None
        elif self.devise == "EUR":
            self.taux_change = devises.PARITE_EURO
        if not self.numero:
            with transaction.atomic():
                annee = self.date.year
                self.numero = f"BC-{annee}-{Compteur.suivant(f'BC-{annee}'):04d}"
                return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)

    @property
    def activite_libelle(self) -> str:
        if self.activite == Activite.AUTRE and self.activite_autre:
            return self.activite_autre
        return self.get_activite_display()

    # ----- montants

    def totaux(self) -> dict:
        """Totaux et ventilation par taux de TVA, arrondis au franc (ou au centime en euro et en dollar)."""
        par_taux = {}
        for ligne in self.lignes.all():
            par_taux[ligne.taux_tva] = par_taux.get(ligne.taux_tva, Decimal(0)) + ligne.montant_ht
        ventilation = [
            {"taux": taux, "base_ht": base, "tva": arrondi(base * taux / CENT, self.devise)}
            for taux, base in sorted(par_taux.items(), reverse=True)
        ]
        for v in ventilation:
            v["ttc"] = v["base_ht"] + v["tva"]
        ht = sum((v["base_ht"] for v in ventilation), Decimal(0))
        tva = sum((v["tva"] for v in ventilation), Decimal(0))
        return {"ventilation": ventilation, "total_ht": ht, "total_tva": tva, "total_ttc": ht + tva,
                "en_lettres": montant_en_lettres(ht + tva, self.devise), "devise": self.devise,
                "contre_valeur_xof": self.en_xof(ht + tva)}

    def en_xof(self, montant):
        """Contre-valeur en francs CFA, ou None si le cours de la devise n'est pas renseigné."""
        if self.devise == "XOF":
            return montant
        return arrondi(montant * self.taux_change) if self.taux_change else None

    # ----- réception

    class Reception(models.TextChoices):
        SANS_OBJET = "", "--"
        AUCUNE = "AUCUNE", "Rien reçu"
        PARTIELLE = "PARTIELLE", "Reçu en partie"
        COMPLETE = "COMPLETE", "Reçu en totalité"

    def quantites_recues(self) -> dict:
        from .reception import quantites_recues

        return quantites_recues(self)

    @property
    def etat_reception(self) -> str:
        if self.statut not in (self.Statut.TRANSMIS, self.Statut.CLOTURE):
            return self.Reception.SANS_OBJET
        recues = self.quantites_recues()
        if not recues:
            return self.Reception.AUCUNE
        complet = all(recues.get(l.id, 0) >= l.quantite for l in self.lignes.all())
        return self.Reception.COMPLETE if complet else self.Reception.PARTIELLE

    def get_etat_reception_display(self) -> str:
        return self.Reception(self.etat_reception).label

    # ----- circuit

    @property
    def modifiable(self) -> bool:
        return self.statut == self.Statut.BROUILLON

    @property
    def definitif(self) -> bool:
        """Vrai quand le bon a ses deux validations et peut être imprimé pour signature."""
        return self.statut in (self.Statut.VALIDE, self.Statut.TRANSMIS, self.Statut.CLOTURE)

    def peut_valider(self, utilisateur) -> bool:
        S = self.Statut
        if self.statut == S.ATTENTE_RESPONSABLE:
            return utilisateur.has_perm("achats.valider_responsable_boncommande")
        if self.statut == S.ATTENTE_CONTROLE:
            return utilisateur.has_perm("achats.valider_controle_boncommande")
        return False

    def peut_preparer(self, utilisateur) -> bool:
        """L'acheteur du bon ou le responsable achats le rédige, le soumet et le transmet."""
        return self.acheteur_id == utilisateur.id or utilisateur.has_perm("achats.valider_responsable_boncommande")

    def _journal(self, utilisateur, action, commentaire=""):
        self.evenements.create(auteur=utilisateur, action=action, statut=self.statut, commentaire=commentaire)

    @transaction.atomic
    def soumettre(self, utilisateur):
        if not self.modifiable:
            raise ValidationError("Ce bon de commande a déjà été soumis.")
        if not self.peut_preparer(utilisateur):
            raise PermissionDenied("Seul l'acheteur du bon ou le responsable achats peut le soumettre.")
        if not self.lignes.exists():
            raise ValidationError("Ajoutez au moins une ligne.")
        self.statut = self.Statut.ATTENTE_RESPONSABLE
        self.save()
        self._journal(utilisateur, EvenementCommande.Action.SOUMISSION)

    @transaction.atomic
    def valider(self, utilisateur, commentaire=""):
        if not self.peut_valider(utilisateur):
            raise PermissionDenied("Vous n'êtes pas le valideur attendu à cette étape.")
        S = self.Statut
        self.statut = S.ATTENTE_CONTROLE if self.statut == S.ATTENTE_RESPONSABLE else S.VALIDE
        self.save()
        self._journal(utilisateur, EvenementCommande.Action.VALIDATION, commentaire)

    @transaction.atomic
    def refuser(self, utilisateur, commentaire):
        """Un valideur renvoie le bon à l'acheteur pour correction."""
        if not self.peut_valider(utilisateur):
            raise PermissionDenied("Vous n'êtes pas le valideur attendu à cette étape.")
        if not commentaire.strip():
            raise ValidationError("Indiquez le motif du refus.")
        self.statut = self.Statut.BROUILLON
        self.save()
        self._journal(utilisateur, EvenementCommande.Action.REFUS, commentaire)

    @transaction.atomic
    def transmettre(self, utilisateur):
        if self.statut != self.Statut.VALIDE:
            raise ValidationError("Seul un bon de commande validé peut être transmis au fournisseur.")
        if not self.peut_preparer(utilisateur):
            raise PermissionDenied("Seul l'acheteur du bon ou le responsable achats peut le transmettre.")
        self.statut = self.Statut.TRANSMIS
        self.transmis_le = timezone.localdate()
        self.save()
        self._journal(utilisateur, EvenementCommande.Action.TRANSMISSION)

    @transaction.atomic
    def cloturer(self, utilisateur, commentaire=""):
        """Solde la commande : plus rien n'est attendu du fournisseur, même si tout n'a pas été reçu."""
        if self.statut != self.Statut.TRANSMIS:
            raise ValidationError("Seul un bon de commande transmis au fournisseur peut être clôturé.")
        if not self.peut_preparer(utilisateur):
            raise PermissionDenied("Seul l'acheteur du bon ou le responsable achats peut le clôturer.")
        if self.etat_reception != self.Reception.COMPLETE and not commentaire.strip():
            raise ValidationError("La commande n'est pas reçue en totalité : indiquez le motif de la clôture.")
        if self.receptions.filter(statut="BROUILLON").exists():
            raise ValidationError("Un bon de réception est en brouillon sur cette commande : validez-le ou annulez-le d'abord.")
        self.statut = self.Statut.CLOTURE
        self.save()
        self._journal(utilisateur, EvenementCommande.Action.CLOTURE, commentaire)

    @transaction.atomic
    def decloturer(self, utilisateur, commentaire=""):
        if self.statut != self.Statut.CLOTURE:
            raise ValidationError("Ce bon de commande n'est pas clôturé.")
        if not self.peut_preparer(utilisateur):
            raise PermissionDenied("Seul l'acheteur du bon ou le responsable achats peut le rouvrir.")
        self.statut = self.Statut.TRANSMIS
        self.save()
        self._journal(utilisateur, EvenementCommande.Action.DECLOTURE, commentaire)

    @transaction.atomic
    def annuler(self, utilisateur, commentaire):
        if self.statut == self.Statut.ANNULE:
            raise ValidationError("Ce bon de commande est déjà annulé.")
        if not utilisateur.has_perm("achats.valider_responsable_boncommande"):
            raise PermissionDenied("Seul le responsable achats peut annuler un bon de commande.")
        if not commentaire.strip():
            raise ValidationError("Indiquez le motif de l'annulation.")
        if self.quantites_recues():
            raise ValidationError("Ce bon de commande a des réceptions validées : annulez-les d'abord.")
        self.statut = self.Statut.ANNULE
        self.save()
        self._journal(utilisateur, EvenementCommande.Action.ANNULATION, commentaire)


class LigneBonCommande(models.Model):
    bon = models.ForeignKey(BonCommande, on_delete=models.CASCADE, related_name="lignes")
    article = models.ForeignKey(Article, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    reference = models.CharField("référence", max_length=100, blank=True)
    designation = models.CharField("désignation", max_length=200)
    quantite = models.DecimalField("quantité", max_digits=12, decimal_places=2)
    prix_unitaire = models.DecimalField("prix unitaire HT", max_digits=14, decimal_places=2)
    remise = models.DecimalField("remise (%)", max_digits=5, decimal_places=2, default=0)
    taux_tva = models.DecimalField("TVA (%)", max_digits=5, decimal_places=2, default=18)

    class Meta:
        verbose_name = "ligne de bon de commande"
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(name="ligne_bc_quantite_positive", condition=models.Q(quantite__gt=0)),
            models.CheckConstraint(name="ligne_bc_prix_positif", condition=models.Q(prix_unitaire__gte=0)),
            models.CheckConstraint(name="ligne_bc_remise_valide", condition=models.Q(remise__gte=0, remise__lte=100)),
            models.CheckConstraint(name="ligne_bc_tva_valide", condition=models.Q(taux_tva__gte=0, taux_tva__lte=100)),
        ]

    @property
    def prix_net(self) -> Decimal:
        return arrondi(self.prix_unitaire * (CENT - self.remise) / CENT, self.bon.devise)

    @property
    def montant_ht(self) -> Decimal:
        return arrondi(self.quantite * self.prix_net, self.bon.devise)


class EvenementCommande(models.Model):
    """Journal du bon de commande : qui a fait quoi et quand."""

    class Action(models.TextChoices):
        SOUMISSION = "SOUMISSION", "Soumission"
        VALIDATION = "VALIDATION", "Validation"
        REFUS = "REFUS", "Refus, à corriger"
        TRANSMISSION = "TRANSMISSION", "Transmission au fournisseur"
        ANNULATION = "ANNULATION", "Annulation"
        CLOTURE = "CLOTURE", "Clôture"
        DECLOTURE = "DECLOTURE", "Réouverture"
        RECEPTION = "RECEPTION", "Réception"
        RECEPTION_ANNULEE = "RECEP_ANNUL", "Réception annulée"

    bon = models.ForeignKey(BonCommande, on_delete=models.CASCADE, related_name="evenements")
    action = models.CharField(max_length=12, choices=Action.choices)
    statut = models.CharField("statut obtenu", max_length=10, choices=BonCommande.Statut.choices)
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    date = models.DateTimeField(auto_now_add=True)
    commentaire = models.TextField(blank=True)

    class Meta:
        verbose_name = "événement de bon de commande"
        ordering = ["id"]
