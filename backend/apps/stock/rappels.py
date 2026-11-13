from django.db.models import Sum


def sous_le_seuil(utilisateur):
    """Articles au seuil d'alerte ou en dessous, pour le responsable du stock."""
    from .models import Mouvement, ReglageStock, nombre

    if not utilisateur.has_perm("stock.ajuster_stock"):
        return None
    quantites = {(m["article"], m["magasin"]): m["q"]
                 for m in Mouvement.objects.values("article", "magasin").annotate(q=Sum("quantite"))}
    lignes = []
    reglages = ReglageStock.objects.filter(seuil_mini__gt=0, article__actif=True).select_related("article", "magasin")
    for r in reglages.order_by("article__designation", "magasin__nom"):
        quantite = quantites.get((r.article_id, r.magasin_id), 0)
        if quantite <= r.seuil_mini:
            lignes.append(f"{r.article.designation} ({r.article.code}) à {r.magasin.nom} : {nombre(quantite) if quantite else '0'} "
                          f"en stock, seuil {nombre(r.seuil_mini)}")
    return "Stock au seuil d'alerte ou en dessous", lignes


# Où traiter chaque rubrique dans l'application (page d'accueil).
sous_le_seuil.lien = "/stock"
