"""Demande de sortie de stock : un atelier ou un service demande des articles, son responsable valide,
le magasin sert. Servir la demande crée le bon de sortie."""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.core.models import Compteur, Horodate, Service
from apps.referentiels.models import Article, Emplacement


class DemandeSortie(Horodate):
    class Statut(models.TextChoices):
        ATTENTE_SERVICE = "ATT_SERVICE", "En attente du responsable de service"
        A_SERVIR = "A_SERVIR", "À servir par le magasin"
        SERVIE = "SERVIE", "Servie"
        REFUSEE = "REFUSEE", "Refusée"
        ANNULEE = "ANNULEE", "Annulée"

    numero = models.CharField("n° de demande", max_length=20, unique=True, editable=False)
    statut = models.CharField(max_length=11, choices=Statut.choices, editable=False)
    demandeur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="demandes_sortie")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="demandes_sortie")
    magasin = models.ForeignKey(Emplacement, on_delete=models.PROTECT, related_name="demandes_sortie",
                                limit_choices_to={"type": "SITE"})
    numero_or = models.CharField("n° d'OR", max_length=40, blank=True)
    materiel = models.CharField("matériel concerné", max_length=100, blank=True)
    motif = models.CharField("motif ou usage", max_length=200, blank=True)
    valide_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, editable=False,
                                   on_delete=models.PROTECT, related_name="+")
    valide_le = models.DateTimeField(null=True, blank=True, editable=False)
    traite_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, editable=False,
                                   on_delete=models.PROTECT, related_name="+")
    traite_le = models.DateTimeField(null=True, blank=True, editable=False)
    motif_refus = models.TextField("motif du refus ou de l'annulation", blank=True, editable=False)
    bon_sortie = models.OneToOneField("stock.BonSortie", null=True, blank=True, editable=False, on_delete=models.PROTECT,
                                      related_name="demande")

    class Meta:
        verbose_name = "demande de sortie"
        verbose_name_plural = "demandes de sortie"
        ordering = ["-cree_le"]

    def __str__(self):
        return self.numero

    @classmethod
    @transaction.atomic
    def creer(cls, utilisateur, lignes, **champs):
        """`lignes` : liste de (article, quantité). La demande part chez le responsable du service, ou directement
        au magasin si le service n'en a pas ou si le demandeur est ce responsable."""
        from .models import exiger_article, exiger_magasin, or_exige

        champs["numero_or"] = (champs.get("numero_or") or "").strip()
        exiger_magasin(champs["magasin"])
        if not lignes:
            raise ValidationError("Indiquez au moins un article.")
        if len({a.id for a, _ in lignes}) != len(lignes):
            raise ValidationError("Un article figure deux fois : regroupez les quantités.")
        for article, quantite in lignes:
            exiger_article(article)
            if quantite <= 0:
                raise ValidationError(f"« {article.designation} » : la quantité doit être positive.")
        if not champs["numero_or"] and or_exige(a for a, _ in lignes):
            raise ValidationError("Le numéro d'OR est obligatoire pour demander une pièce.")
        responsable = champs["service"].responsable_id
        direct = responsable is None or responsable == utilisateur.id
        annee = timezone.localdate().year
        demande = cls.objects.create(
            numero=f"DS-{annee}-{Compteur.suivant(f'DS-{annee}'):04d}", demandeur=utilisateur,
            statut=cls.Statut.A_SERVIR if direct else cls.Statut.ATTENTE_SERVICE,
            cree_par=utilisateur, modifie_par=utilisateur, **champs)
        LigneDemandeSortie.objects.bulk_create(LigneDemandeSortie(demande=demande, article=a, quantite=q) for a, q in lignes)
        return demande

    # ----- qui peut quoi

    def peut_valider(self, u) -> bool:
        return self.statut == self.Statut.ATTENTE_SERVICE and self.service.responsable_id == u.id

    def peut_servir(self, u) -> bool:
        return self.statut == self.Statut.A_SERVIR and u.has_perm("stock.add_bonsortie")

    def peut_refuser(self, u) -> bool:
        return self.peut_valider(u) or self.peut_servir(u)

    def peut_annuler(self, u) -> bool:
        return self.demandeur_id == u.id and self.statut in (self.Statut.ATTENTE_SERVICE, self.Statut.A_SERVIR)

    # ----- circuit

    def valider(self, utilisateur):
        if not self.peut_valider(utilisateur):
            raise PermissionDenied("Seul le responsable du service valide cette demande.")
        self.statut, self.valide_par, self.valide_le = self.Statut.A_SERVIR, utilisateur, timezone.now()
        self.modifie_par = utilisateur
        self.save()

    def _fermer(self, utilisateur, statut, commentaire):
        if not commentaire.strip():
            raise ValidationError("Indiquez le motif.")
        self.statut, self.motif_refus = statut, commentaire.strip()
        self.traite_par, self.traite_le, self.modifie_par = utilisateur, timezone.now(), utilisateur
        self.save()

    def refuser(self, utilisateur, commentaire):
        if not self.peut_refuser(utilisateur):
            raise PermissionDenied("Vous ne pouvez pas refuser cette demande.")
        self._fermer(utilisateur, self.Statut.REFUSEE, commentaire)

    def annuler(self, utilisateur, commentaire):
        if not self.peut_annuler(utilisateur):
            raise PermissionDenied("Seul le demandeur annule sa demande, tant qu'elle n'est pas servie.")
        self._fermer(utilisateur, self.Statut.ANNULEE, commentaire)

    @transaction.atomic
    def servir(self, utilisateur, quantites=None):
        """Le magasin remet les articles : crée le bon de sortie. `quantites` : {id de ligne: quantité servie} ;
        sans lui, tout est servi. Ce qui n'est pas servi fera l'objet d'une nouvelle demande."""
        from .models import BonSortie

        if not self.peut_servir(utilisateur):
            raise PermissionDenied("Seul le magasin sert une demande validée.")
        a_sortir = []
        lignes = list(self.lignes.select_related("article"))
        for ligne in lignes:
            servie = ligne.quantite if quantites is None else Decimal(str(quantites.get(ligne.id, quantites.get(str(ligne.id), 0)) or 0))
            if servie < 0 or servie > ligne.quantite:
                raise ValidationError(f"« {ligne.article.designation} » : on ne sert pas plus que la quantité demandée.")
            ligne.quantite_servie = servie
            if servie > 0:
                a_sortir.append((ligne.article, servie))
        if not a_sortir:
            raise ValidationError("Rien à servir : indiquez une quantité, ou refusez la demande.")
        self.bon_sortie = BonSortie.enregistrer(
            utilisateur, a_sortir, magasin=self.magasin, numero_or=self.numero_or, materiel=self.materiel,
            remis_a=self.demandeur, service=self.service, observations=f"Demande {self.numero}. {self.motif}".strip())
        LigneDemandeSortie.objects.bulk_update(lignes, ["quantite_servie"])
        self.statut, self.traite_par, self.traite_le = self.Statut.SERVIE, utilisateur, timezone.now()
        self.modifie_par = utilisateur
        self.save()


class LigneDemandeSortie(models.Model):
    demande = models.ForeignKey(DemandeSortie, on_delete=models.CASCADE, related_name="lignes")
    article = models.ForeignKey(Article, on_delete=models.PROTECT, related_name="+")
    quantite = models.DecimalField("quantité demandée", max_digits=12, decimal_places=2)
    quantite_servie = models.DecimalField("quantité servie", max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name = "ligne de demande de sortie"
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(name="ligne_ds_quantite_positive", condition=models.Q(quantite__gt=0)),
            models.UniqueConstraint(fields=["demande", "article"], name="ligne_ds_article_unique"),
        ]
