"""Stock : ce qu'il y a dans chaque magasin, et tout ce qui y entre ou en sort.

Le stock n'est jamais saisi directement : c'est la somme des mouvements. Un mouvement ne se modifie pas et ne se
supprime pas ; une erreur se corrige par un mouvement inverse. Un magasin est un emplacement de type « site »."""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone

from apps.achats.reception import LigneBonReception
from apps.core.models import Compteur, Horodate, Service
from apps.referentiels.models import Article, Emplacement

ZERO = Decimal(0)


def nombre(q: Decimal) -> str:
    return f"{q.normalize():f}"


class Mouvement(models.Model):
    class Type(models.TextChoices):
        RECEPTION = "RECEPTION", "Entrée sur bon de réception"
        SORTIE = "SORTIE", "Sortie"
        TRANSFERT = "TRANSFERT", "Transfert entre magasins"
        INVENTAIRE = "INVENTAIRE", "Ajustement d'inventaire"
        ANNULATION = "ANNULATION", "Annulation"

    article = models.ForeignKey(Article, on_delete=models.PROTECT, related_name="mouvements")
    magasin = models.ForeignKey(Emplacement, on_delete=models.PROTECT, related_name="mouvements")
    date = models.DateTimeField(default=timezone.now)
    type = models.CharField(max_length=10, choices=Type.choices)
    quantite = models.DecimalField("quantité", max_digits=12, decimal_places=2, help_text="Positive : entrée. Négative : sortie.")
    prix_unitaire = models.DecimalField("prix unitaire (XOF)", max_digits=14, decimal_places=2, null=True, blank=True)
    ligne_reception = models.ForeignKey(LigneBonReception, null=True, blank=True, on_delete=models.PROTECT,
                                        related_name="mouvements_stock")
    ligne_sortie = models.ForeignKey("LigneBonSortie", null=True, blank=True, on_delete=models.PROTECT,
                                     related_name="mouvements")
    motif = models.CharField(max_length=200, blank=True)
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        verbose_name = "mouvement de stock"
        verbose_name_plural = "mouvements de stock"
        ordering = ["-date", "-id"]
        indexes = [models.Index(fields=["article", "magasin"])]
        constraints = [models.CheckConstraint(name="mouvement_quantite_non_nulle", condition=~models.Q(quantite=0))]
        permissions = [("ajuster_stock", "Peut ajuster le stock (inventaire) et transférer entre magasins")]

    def __str__(self):
        return f"{self.get_type_display()} {self.quantite:+} {self.article.code}"


def verrouiller():
    """Fait passer les écritures de stock une par une, pour que deux sorties ne prennent pas la même pièce.
    À appeler dans une transaction, avant de lire le stock."""
    Compteur.objects.select_for_update().get_or_create(cle="STOCK-VERROU")


def quantite_en_stock(article, magasin) -> Decimal:
    return Mouvement.objects.filter(article=article, magasin=magasin).aggregate(q=Sum("quantite"))["q"] or ZERO


def exiger_magasin(magasin):
    if magasin.type != Emplacement.Type.SITE:
        raise ValidationError("Le stock se tient dans un magasin de l'entreprise, pas sur un site client.")


def exiger_article(article):
    if not article.gere_en_stock:
        raise ValidationError(f"« {article.designation} » n'est pas un article géré en stock.")


def sortir(article, magasin, quantite, **champs):
    """Écrit une sortie après avoir vérifié qu'il y a assez en stock. Le verrou doit être pris."""
    dispo = quantite_en_stock(article, magasin)
    if quantite > dispo:
        raise ValidationError(
            f"« {article.designation} » : {nombre(quantite)} demandé pour {nombre(dispo)} en stock à {magasin.nom}.")
    return Mouvement.objects.create(article=article, magasin=magasin, quantite=-quantite, **champs)


def _exiger_droit_ajuster(utilisateur):
    if not utilisateur.has_perm("stock.ajuster_stock"):
        raise PermissionDenied("Seul le responsable du stock peut ajuster ou transférer le stock.")


@transaction.atomic
def ajuster(utilisateur, article, magasin, quantite_comptee, motif, prix_unitaire=None):
    """Inventaire : met le stock à la quantité comptée. Sert aussi à saisir le stock de départ."""
    _exiger_droit_ajuster(utilisateur)
    exiger_magasin(magasin)
    exiger_article(article)
    if quantite_comptee < 0:
        raise ValidationError("La quantité comptée ne peut pas être négative.")
    if not motif.strip():
        raise ValidationError("Indiquez le motif de l'ajustement (inventaire, stock de départ, casse...).")
    verrouiller()
    ecart = quantite_comptee - quantite_en_stock(article, magasin)
    if ecart == 0:
        raise ValidationError("Le stock est déjà à cette quantité.")
    return Mouvement.objects.create(article=article, magasin=magasin, type=Mouvement.Type.INVENTAIRE, quantite=ecart,
                                    prix_unitaire=prix_unitaire, motif=motif.strip()[:200], auteur=utilisateur)


@transaction.atomic
def transferer(utilisateur, article, origine, destination, quantite, motif=""):
    _exiger_droit_ajuster(utilisateur)
    exiger_magasin(origine)
    exiger_magasin(destination)
    exiger_article(article)
    if origine == destination:
        raise ValidationError("Choisissez deux magasins différents.")
    if quantite <= 0:
        raise ValidationError("La quantité à transférer doit être positive.")
    verrouiller()
    champs = dict(type=Mouvement.Type.TRANSFERT, auteur=utilisateur)
    sortir(article, origine, quantite, motif=f"Vers {destination.nom}. {motif}".strip()[:200], **champs)
    return Mouvement.objects.create(article=article, magasin=destination, quantite=quantite,
                                    motif=f"Depuis {origine.nom}. {motif}".strip()[:200], **champs)


class ReglageStock(models.Model):
    """Seuil d'alerte et rangement d'un article dans un magasin."""

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="reglages_stock")
    magasin = models.ForeignKey(Emplacement, on_delete=models.CASCADE, related_name="reglages_stock")
    seuil_mini = models.DecimalField("seuil d'alerte", max_digits=12, decimal_places=2, default=0)
    casier = models.CharField("rangement (allée, casier)", max_length=40, blank=True)

    class Meta:
        verbose_name = "réglage de stock"
        verbose_name_plural = "réglages de stock"
        constraints = [
            models.UniqueConstraint(fields=["article", "magasin"], name="reglage_stock_unique"),
            models.CheckConstraint(name="reglage_stock_seuil_positif", condition=models.Q(seuil_mini__gte=0)),
        ]


class BonSortie(Horodate):
    """Sortie de pièces du magasin pour un ordre de réparation (OR). Sans numéro d'OR, rien ne sort."""

    class Statut(models.TextChoices):
        VALIDE = "VALIDE", "Validé"
        ANNULE = "ANNULE", "Annulé"

    numero = models.CharField("n° de bon de sortie", max_length=20, unique=True, editable=False)
    statut = models.CharField(max_length=8, choices=Statut.choices, default=Statut.VALIDE, editable=False)
    date = models.DateField("date de sortie", default=timezone.localdate)
    magasin = models.ForeignKey(Emplacement, on_delete=models.PROTECT, related_name="bons_sortie",
                                limit_choices_to={"type": "SITE"})
    numero_or = models.CharField("n° d'OR", max_length=40)
    materiel = models.CharField("matériel concerné", max_length=100, blank=True, help_text="Engin, véhicule, immatriculation")
    remis_a = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sorties_recues",
                                verbose_name="remis à")
    service = models.ForeignKey(Service, null=True, blank=True, on_delete=models.PROTECT, related_name="bons_sortie")
    observations = models.TextField(blank=True)
    magasinier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sorties_faites")
    annule_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, editable=False,
                                   on_delete=models.PROTECT, related_name="+")
    annule_le = models.DateTimeField("annulé le", null=True, blank=True, editable=False)
    motif_annulation = models.TextField("motif de l'annulation", blank=True, editable=False)

    class Meta:
        verbose_name = "bon de sortie"
        verbose_name_plural = "bons de sortie"
        ordering = ["-cree_le"]
        permissions = [("annuler_bonsortie", "Peut annuler un bon de sortie")]
        constraints = [models.CheckConstraint(name="bon_sortie_or_obligatoire", condition=~models.Q(numero_or=""))]

    def __str__(self):
        return self.numero

    @classmethod
    @transaction.atomic
    def enregistrer(cls, utilisateur, lignes, **champs):
        """Crée le bon et sort les pièces du stock. `lignes` : liste de (article, quantité)."""
        if not utilisateur.has_perm("stock.add_bonsortie"):
            raise PermissionDenied("Seul le magasin enregistre les sorties de stock.")
        champs["numero_or"] = (champs.get("numero_or") or "").strip()
        if not champs["numero_or"]:
            raise ValidationError("Le numéro d'OR est obligatoire pour sortir une pièce du stock.")
        exiger_magasin(champs["magasin"])
        if not lignes:
            raise ValidationError("Indiquez au moins une pièce à sortir.")
        articles = [a.id for a, _ in lignes]
        if len(set(articles)) != len(articles):
            raise ValidationError("Un article figure deux fois : regroupez les quantités.")
        verrouiller()
        annee = champs.get("date", timezone.localdate()).year
        bon = cls.objects.create(numero=f"BS-{annee}-{Compteur.suivant(f'BS-{annee}'):04d}", magasinier=utilisateur,
                                 cree_par=utilisateur, modifie_par=utilisateur, **champs)
        for article, quantite in lignes:
            exiger_article(article)
            if quantite <= 0:
                raise ValidationError(f"« {article.designation} » : la quantité doit être positive.")
            ligne = bon.lignes.create(article=article, quantite=quantite)
            sortir(article, bon.magasin, quantite, type=Mouvement.Type.SORTIE, ligne_sortie=ligne,
                   motif=f"{bon.numero} · OR : {bon.numero_or}"[:200], auteur=utilisateur)
        return bon

    def peut_annuler(self, utilisateur) -> bool:
        return self.statut == self.Statut.VALIDE and utilisateur.has_perm("stock.annuler_bonsortie")

    @transaction.atomic
    def annuler(self, utilisateur, commentaire):
        """Annule le bon : les pièces reviennent en stock."""
        if not utilisateur.has_perm("stock.annuler_bonsortie"):
            raise PermissionDenied("Seul le responsable du stock peut annuler un bon de sortie.")
        if self.statut != self.Statut.VALIDE:
            raise ValidationError("Ce bon de sortie est déjà annulé.")
        if not commentaire.strip():
            raise ValidationError("Indiquez le motif de l'annulation.")
        verrouiller()
        for ligne in self.lignes.select_related("article"):
            Mouvement.objects.create(article=ligne.article, magasin=self.magasin, type=Mouvement.Type.ANNULATION,
                                     quantite=ligne.quantite, ligne_sortie=ligne,
                                     motif=f"Annulation de {self.numero}"[:200], auteur=utilisateur)
        self.statut = self.Statut.ANNULE
        self.annule_par, self.annule_le, self.motif_annulation = utilisateur, timezone.now(), commentaire.strip()
        self.modifie_par = utilisateur
        self.save()


class LigneBonSortie(models.Model):
    bon = models.ForeignKey(BonSortie, on_delete=models.CASCADE, related_name="lignes")
    article = models.ForeignKey(Article, on_delete=models.PROTECT, related_name="+")
    quantite = models.DecimalField("quantité", max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "ligne de bon de sortie"
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(name="ligne_bs_quantite_positive", condition=models.Q(quantite__gt=0)),
            models.UniqueConstraint(fields=["bon", "article"], name="ligne_bs_article_unique"),
        ]
