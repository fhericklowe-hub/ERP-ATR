from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.core.models import Compteur, Horodate, Service, Site
from apps.referentiels.models import Article, Unite

from . import delais


class Acheteur(models.Model):
    """Membre de l'équipe achats à qui des demandes peuvent être attribuées."""

    utilisateur = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="acheteur")
    disponible = models.BooleanField(
        default=True, help_text="Décocher pendant une absence : les nouvelles demandes vont aux autres acheteurs."
    )

    class Meta:
        ordering = ["utilisateur__last_name", "utilisateur__first_name"]

    def __str__(self):
        return str(self.utilisateur)

    @classmethod
    def avec_charge(cls):
        """Acheteurs avec leur nombre de demandes en cours de traitement."""
        # En cours : la demande est aux achats, ou validée mais sans bon de commande validé.
        d = "utilisateur__demandes_attribuees"
        commandee = models.Exists(
            BonCommande.objects.filter(demande=models.OuterRef(f"{d}__pk"), statut__in=["VALIDE", "TRANSMIS"])
        )
        en_cours = models.Count(
            d, distinct=True,
            filter=models.Q(**{f"{d}__statut": DemandeAchat.Statut.ATTENTE_ACHATS})
            | (models.Q(**{f"{d}__statut": DemandeAchat.Statut.VALIDEE}) & ~commandee),
        )
        return (
            cls.objects.select_related("utilisateur").annotate(en_cours=en_cours)
            .order_by("utilisateur__last_name", "utilisateur__first_name", "id")
        )

    @classmethod
    def choisir(cls):
        """L'acheteur disponible le moins chargé ; à égalité, celui servi le moins récemment."""
        dernier = models.Max("utilisateur__demandes_attribuees__recue_le")
        return (
            cls.avec_charge()
            .filter(disponible=True, utilisateur__is_active=True)
            .annotate(dernier=dernier)
            .order_by("en_cours", models.F("dernier").asc(nulls_first=True), "id")
            .first()
        )


class DemandeAchat(Horodate):
    """Demande d'achat et son circuit : service demandeur, direction technique si urgent, achats."""

    class Statut(models.TextChoices):
        BROUILLON = "BROUILLON", "Brouillon"
        ATTENTE_SERVICE = "ATT_SERVICE", "En attente du responsable de service"
        ATTENTE_DT = "ATT_DT", "En attente du directeur technique"
        ATTENTE_ACHATS = "ATT_ACHATS", "En attente des achats"
        RENVOYEE = "RENVOYEE", "Renvoyée au demandeur (incomplète)"
        VALIDEE = "VALIDEE", "Validée"
        REFUSEE = "REFUSEE", "Refusée"

    class Urgence(models.IntegerChoices):
        URGENT = 1, "1. Urgent (machine ou activité à l'arrêt)"
        NORMAL = 2, "2. Normal (besoin courant)"
        PLANIFIE = 3, "3. Planifié (préventif, réapprovisionnement)"

    class Activite(models.TextChoices):
        MANUTENTION = "MANUTENTION", "Manutention"
        LEVAGE = "LEVAGE", "Levage"
        TRANSPORT = "TRANSPORT", "Transport"
        AUTRE = "AUTRE", "Autre"

    class ControleStock(models.TextChoices):
        NON_FAIT = "", "Non contrôlé"
        DISPONIBLE = "DISPO", "Disponible"
        NON_DISPONIBLE = "NON_DISPO", "Non disponible"

    numero = models.CharField("n° DA", max_length=20, unique=True, editable=False)
    ancien_numero = models.CharField("n° dans l'ancien logiciel", max_length=30, blank=True)
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.BROUILLON, editable=False)
    date_demande = models.DateField("date de la demande", default=timezone.localdate)

    # 1. Demandeur
    demandeur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="demandes_achat")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="demandes_achat")
    site = models.ForeignKey(Site, on_delete=models.PROTECT, related_name="demandes_achat")
    telephone = models.CharField("téléphone", max_length=30, blank=True)
    numero_or = models.CharField("numéro OR", max_length=30, blank=True)
    date_besoin = models.DateField("date de besoin souhaitée", null=True, blank=True)

    # 2. Équipement concerné (obligatoire pour les pièces techniques)
    piece_technique = models.BooleanField("pièces techniques", default=False)
    equipement_designation = models.CharField("désignation de l'équipement", max_length=150, blank=True)
    equipement_marque = models.CharField("marque", max_length=100, blank=True)
    equipement_modele = models.CharField("modèle", max_length=100, blank=True)
    equipement_serie = models.CharField("n° de série / immatriculation", max_length=100, blank=True)
    activite = models.CharField("activité", max_length=12, choices=Activite.choices, blank=True)
    activite_autre = models.CharField("autre activité", max_length=100, blank=True)

    # 4. Urgence
    urgence = models.PositiveSmallIntegerField(choices=Urgence.choices, default=Urgence.NORMAL)
    justification_urgence = models.TextField("justification de l'urgence", blank=True)

    # Cadre réservé au service achats
    recue_le = models.DateTimeField("fiche complète reçue le", null=True, blank=True, editable=False)
    echeance_commande = models.DateTimeField("bon de commande attendu avant le", null=True, blank=True, editable=False)
    elements_manquants = models.TextField("éléments manquants", blank=True, editable=False)
    controle_stock = models.CharField(max_length=10, choices=ControleStock.choices, blank=True, default="")
    acheteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, editable=False, on_delete=models.PROTECT,
        related_name="demandes_attribuees", verbose_name="acheteur chargé de la demande",
    )

    class Meta:
        verbose_name = "demande d'achat"
        verbose_name_plural = "demandes d'achat"
        ordering = ["-cree_le"]
        permissions = [
            ("voir_toutes_demandeachat", "Peut voir les demandes d'achat de tous les services"),
            ("valider_direction_technique_demandeachat", "Peut valider les demandes urgentes (directeur technique)"),
            ("valider_achats_demandeachat", "Peut valider les demandes d'achat (service achats)"),
        ]

    def __str__(self):
        return self.numero

    def save(self, *args, **kwargs):
        if not self.numero:
            with transaction.atomic():
                annee = self.date_demande.year
                self.numero = f"DA-{annee}-{Compteur.suivant(f'DA-{annee}'):04d}"
                return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)

    # ----- règles du circuit

    @property
    def modifiable(self) -> bool:
        return self.statut in (self.Statut.BROUILLON, self.Statut.RENVOYEE)

    @property
    def en_retard(self) -> bool:
        return (
            self.statut == self.Statut.ATTENTE_ACHATS
            and self.echeance_commande is not None
            and timezone.now() > self.echeance_commande
        )

    def peut_valider(self, utilisateur) -> bool:
        """Vrai si l'utilisateur est le valideur attendu à l'étape en cours."""
        S = self.Statut
        if self.statut == S.ATTENTE_SERVICE:
            return self.service.responsable_id == utilisateur.id
        if self.statut == S.ATTENTE_DT:
            return utilisateur.has_perm("achats.valider_direction_technique_demandeachat")
        if self.statut == S.ATTENTE_ACHATS:
            return utilisateur.has_perm("achats.valider_achats_demandeachat")
        return False

    def peut_traiter(self, utilisateur) -> bool:
        """Vrai pour l'acheteur chargé de la demande et pour le responsable achats, tant qu'elle est aux achats."""
        return self.statut == self.Statut.ATTENTE_ACHATS and (
            self.acheteur_id == utilisateur.id or utilisateur.has_perm("achats.valider_achats_demandeachat")
        )

    def controler_completude(self):
        erreurs = []
        if not self.lignes.exists():
            erreurs.append("Ajoutez au moins un article.")
        if self.urgence == self.Urgence.URGENT and not self.justification_urgence.strip():
            erreurs.append("La justification est obligatoire pour une demande urgente.")
        if self.piece_technique:
            if not (self.equipement_designation and self.equipement_serie):
                erreurs.append("Pour des pièces techniques, indiquez l'équipement et son n° de série ou immatriculation.")
            if not self.pieces_jointes.exists():
                erreurs.append("Pour des pièces techniques, joignez une photo de la pièce ou de la plaque signalétique.")
        if not self.service.responsable_id:
            erreurs.append(f"Le service {self.service} n'a pas de responsable désigné pour valider la demande.")
        if erreurs:
            raise ValidationError(erreurs)

    def _journal(self, utilisateur, action, commentaire=""):
        self.evenements.create(auteur=utilisateur, action=action, statut=self.statut, commentaire=commentaire)

    def _arriver_aux_achats(self):
        """Entrée dans l'équipe achats : attribution à un acheteur et départ du délai."""
        self.statut = self.Statut.ATTENTE_ACHATS
        deja = Acheteur.objects.filter(utilisateur_id=self.acheteur_id, disponible=True, utilisateur__is_active=True)
        if not deja.exists():  # une demande renvoyée puis corrigée revient au même acheteur s'il est disponible
            choisi = Acheteur.choisir()
            self.acheteur = choisi.utilisateur if choisi else None
        self.recue_le = timezone.now()
        local = timezone.localtime(self.recue_le)
        if self.urgence == self.Urgence.URGENT:
            self.echeance_commande = delais.ajouter_heures_ouvrees(local, 4)
        else:
            self.echeance_commande = delais.ajouter_jours_ouvres(local, 2 if self.urgence == self.Urgence.NORMAL else 3)

    @transaction.atomic
    def soumettre(self, utilisateur):
        if not self.modifiable:
            raise ValidationError("Cette demande a déjà été soumise.")
        if utilisateur.id != self.demandeur_id:
            raise PermissionDenied("Seul le demandeur peut soumettre sa demande.")
        self.controler_completude()
        self.statut = self.Statut.ATTENTE_SERVICE
        self.elements_manquants = ""
        self.save()
        self._journal(utilisateur, Evenement.Action.SOUMISSION)

    @transaction.atomic
    def valider(self, utilisateur, commentaire=""):
        if not self.peut_valider(utilisateur):
            raise PermissionDenied("Vous n'êtes pas le valideur attendu à cette étape.")
        S = self.Statut
        avant = self.statut
        if self.statut == S.ATTENTE_SERVICE:
            if self.urgence == self.Urgence.URGENT:
                self.statut = S.ATTENTE_DT
            else:
                self._arriver_aux_achats()
        elif self.statut == S.ATTENTE_DT:
            self._arriver_aux_achats()
        else:
            self.statut = S.VALIDEE
        self.save()
        self._journal(utilisateur, Evenement.Action.VALIDATION, commentaire)
        if avant != S.ATTENTE_ACHATS and self.statut == S.ATTENTE_ACHATS:
            self._journal(
                utilisateur, Evenement.Action.ATTRIBUTION,
                f"Attribuée automatiquement à {self.acheteur}" if self.acheteur_id else "Aucun acheteur disponible",
            )

    @transaction.atomic
    def refuser(self, utilisateur, commentaire):
        if not self.peut_valider(utilisateur):
            raise PermissionDenied("Vous n'êtes pas le valideur attendu à cette étape.")
        if not commentaire.strip():
            raise ValidationError("Indiquez le motif du refus.")
        self.statut = self.Statut.REFUSEE
        self.save()
        self._journal(utilisateur, Evenement.Action.REFUS, commentaire)

    @transaction.atomic
    def renvoyer(self, utilisateur, elements_manquants):
        """Le service achats renvoie une fiche incomplète au demandeur."""
        if not self.peut_traiter(utilisateur):
            raise PermissionDenied("Seul l'acheteur chargé de la demande ou le responsable achats peut la renvoyer.")
        if not elements_manquants.strip():
            raise ValidationError("Indiquez les éléments manquants.")
        self.statut = self.Statut.RENVOYEE
        self.elements_manquants = elements_manquants
        self.recue_le = self.echeance_commande = None  # le délai repart à la réception de la fiche complète
        self.save()
        self._journal(utilisateur, Evenement.Action.RENVOI, elements_manquants)

    @transaction.atomic
    def attribuer(self, utilisateur, acheteur):
        """Le responsable achats confie la demande à un autre acheteur."""
        if self.statut != self.Statut.ATTENTE_ACHATS or not utilisateur.has_perm("achats.valider_achats_demandeachat"):
            raise PermissionDenied("Seul le responsable achats peut attribuer une demande reçue par les achats.")
        self.acheteur = acheteur.utilisateur
        self.save()
        self._journal(utilisateur, Evenement.Action.ATTRIBUTION, f"Attribuée à {acheteur}")


class LigneDemandeAchat(models.Model):
    demande = models.ForeignKey(DemandeAchat, on_delete=models.CASCADE, related_name="lignes")
    article = models.ForeignKey(Article, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    designation = models.CharField("désignation", max_length=200)
    reference_constructeur = models.CharField("référence constructeur / n° de pièce", max_length=100, blank=True)
    quantite = models.DecimalField("quantité", max_digits=12, decimal_places=2)
    unite = models.ForeignKey(Unite, on_delete=models.PROTECT, related_name="+", verbose_name="unité")
    observations = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "ligne de demande d'achat"
        ordering = ["id"]
        constraints = [models.CheckConstraint(name="ligne_da_quantite_positive", condition=models.Q(quantite__gt=0))]

    def __str__(self):
        return f"{self.quantite} {self.unite} {self.designation}"


def chemin_piece_jointe(instance, nom):
    return f"achats/demandes/{instance.demande_id}/{nom}"


class PieceJointe(models.Model):
    demande = models.ForeignKey(DemandeAchat, on_delete=models.CASCADE, related_name="pieces_jointes")
    fichier = models.FileField(upload_to=chemin_piece_jointe)
    ajoutee_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    ajoutee_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "pièce jointe"
        verbose_name_plural = "pièces jointes"
        ordering = ["id"]


class Evenement(models.Model):
    """Journal du circuit : qui a fait quoi et quand. Tient lieu de signatures."""

    class Action(models.TextChoices):
        SOUMISSION = "SOUMISSION", "Soumission"
        VALIDATION = "VALIDATION", "Validation"
        REFUS = "REFUS", "Refus"
        RENVOI = "RENVOI", "Renvoi au demandeur"
        ATTRIBUTION = "ATTRIBUTION", "Attribution à un acheteur"

    demande = models.ForeignKey(DemandeAchat, on_delete=models.CASCADE, related_name="evenements")
    action = models.CharField(max_length=12, choices=Action.choices)
    statut = models.CharField("statut obtenu", max_length=12, choices=DemandeAchat.Statut.choices)
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    date = models.DateTimeField(auto_now_add=True)
    commentaire = models.TextField(blank=True)

    class Meta:
        verbose_name = "événement"
        ordering = ["id"]


# Les modèles du bon de commande vivent dans leur propre fichier.
from .commande import BonCommande, EvenementCommande, LigneBonCommande  # noqa: E402,F401
