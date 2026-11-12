"""Temps passé et coût d'un ordre de réparation.

Le coût additionne la main-d'œuvre (heures saisies × taux horaire de l'atelier au jour de la saisie) et les pièces
sorties du stock pour l'OR, comptées au dernier prix d'entrée connu de l'article."""
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

ZERO = Decimal(0)
CENTIME = Decimal("0.01")


class ReglageAtelier(models.Model):
    """Une seule ligne : les réglages de l'atelier."""

    taux_horaire = models.DecimalField("taux horaire de main-d'œuvre (XOF)", max_digits=12, decimal_places=2, null=True,
                                       blank=True, validators=[MinValueValidator(0)],
                                       help_text="Coût moyen d'une heure de mécanicien. Laissez vide pour ne pas chiffrer "
                                                 "la main-d'œuvre. Un changement ne touche pas les heures déjà saisies.")

    class Meta:
        verbose_name = "réglages de l'atelier"
        verbose_name_plural = "réglages de l'atelier"

    def __str__(self):
        return "Réglages de l'atelier"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def taux(cls):
        reglage = cls.objects.filter(pk=1).first()
        return reglage.taux_horaire if reglage else None


class TempsPasse(models.Model):
    ordre = models.ForeignKey("technique.OrdreReparation", on_delete=models.CASCADE, related_name="temps")
    mecanicien = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="temps_atelier",
                                   verbose_name="mécanicien")
    date = models.DateField(default=timezone.localdate)
    heures = models.DecimalField(max_digits=4, decimal_places=2,
                                 validators=[MinValueValidator(Decimal("0.25")), MaxValueValidator(24)])
    taux_horaire = models.DecimalField("taux horaire (XOF)", max_digits=12, decimal_places=2, null=True, blank=True,
                                       editable=False)
    commentaire = models.CharField(max_length=200, blank=True)
    saisi_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+",
                                  editable=False)
    saisi_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "temps passé"
        verbose_name_plural = "temps passés"
        ordering = ["date", "id"]

    def __str__(self):
        return f"{self.ordre} · {self.mecanicien} · {self.heures} h"

    @property
    def montant(self):
        return None if self.taux_horaire is None else (self.heures * self.taux_horaire).quantize(CENTIME)


def prix_des_articles(articles, avant) -> dict:
    """Dernier prix d'entrée connu de chaque article à la date donnée ; à défaut, le premier prix connu ensuite."""
    from apps.stock.models import Mouvement

    prix = {}
    entrees = Mouvement.objects.filter(article__in=articles, quantite__gt=0, prix_unitaire__isnull=False)
    for article_id, date, pu in entrees.order_by("date", "id").values_list("article_id", "date", "prix_unitaire"):
        if date <= avant or article_id not in prix:
            prix[article_id] = pu
    return prix


def pieces(ordre) -> list:
    """Lignes sorties du stock pour l'OR, avec leur prix unitaire et leur montant (None si le prix est inconnu)."""
    lignes = []
    for bon in ordre.sorties().prefetch_related("lignes__article__unite").order_by("date", "id"):
        bon_lignes = list(bon.lignes.all())
        prix = prix_des_articles([l.article_id for l in bon_lignes], bon.cree_le)
        for l in bon_lignes:
            pu = prix.get(l.article_id)
            lignes.append({"bon": bon.id, "bon_numero": bon.numero, "date": bon.date, "code": l.article.code,
                           "designation": l.article.designation, "quantite": l.quantite, "unite": l.article.unite.code,
                           "prix_unitaire": pu, "montant": None if pu is None else (l.quantite * pu).quantize(CENTIME)})
    return lignes


def cout(ordre, lignes=None) -> dict:
    lignes = pieces(ordre) if lignes is None else lignes
    temps = list(ordre.temps.all())
    main_oeuvre = sum((t.montant for t in temps if t.montant is not None), ZERO)
    total_pieces = sum((l["montant"] for l in lignes if l["montant"] is not None), ZERO)
    return {"heures": sum((t.heures for t in temps), ZERO), "main_oeuvre": main_oeuvre, "pieces": total_pieces,
            "total": main_oeuvre + total_pieces,
            "heures_non_chiffrees": sum((t.heures for t in temps if t.montant is None), ZERO),
            "pieces_sans_prix": sum(1 for l in lignes if l["montant"] is None)}
