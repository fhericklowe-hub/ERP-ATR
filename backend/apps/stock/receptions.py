"""Lien entre les bons de réception des achats et le stock."""
from django.core.exceptions import ValidationError

from .models import Mouvement, sortir, verrouiller


def _lignes_a_stocker(bon):
    """Lignes dont une quantité va en stock et dont l'article du catalogue est géré en stock."""
    for ligne in bon.lignes.select_related("ligne_commande__article", "ligne_commande__bon"):
        article = ligne.ligne_commande.article
        if ligne.quantite_stock > 0 and article and article.gere_en_stock:
            yield ligne, article


def entrer_en_stock(sender, bon, utilisateur, **kwargs):
    """À la validation d'un bon de réception : la « quantité à mettre en stock » entre dans le magasin."""
    if not bon.magasin_id:
        return
    for ligne, article in _lignes_a_stocker(bon):
        lc = ligne.ligne_commande
        prix = lc.bon.en_xof(lc.prix_net)  # None si le cours de la devise n'est pas connu
        Mouvement.objects.create(article=article, magasin=bon.magasin, type=Mouvement.Type.RECEPTION,
                                 quantite=ligne.quantite_stock, prix_unitaire=prix, ligne_reception=ligne,
                                 motif=f"{bon.numero}, commande {lc.bon.numero}"[:200], auteur=utilisateur)


def annuler_entree(sender, bon, utilisateur, **kwargs):
    """À l'annulation d'un bon de réception validé : ce qui était entré ressort, s'il est encore là."""
    entrees = list(Mouvement.objects.filter(ligne_reception__bon=bon, type=Mouvement.Type.RECEPTION).select_related("article", "magasin"))
    if not entrees:
        return
    verrouiller()
    for entree in entrees:
        try:
            sortir(entree.article, entree.magasin, entree.quantite, type=Mouvement.Type.ANNULATION,
                   ligne_reception=entree.ligne_reception, motif=f"Annulation de {bon.numero}"[:200], auteur=utilisateur)
        except ValidationError:
            raise ValidationError(
                f"« {entree.article.designation} » reçu sur ce bon est déjà sorti du stock : "
                "annulez d'abord le bon de sortie, ou corrigez par un ajustement d'inventaire.")
