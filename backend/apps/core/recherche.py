"""Recherche globale : un mot cherché dans tous les modules auxquels l'utilisateur a droit.

Chaque source reprend la vue de liste du module : mêmes droits, même périmètre de lignes, mêmes champs de recherche.
Une rubrique que l'utilisateur ne peut pas consulter ne renvoie donc rien."""
from urllib.parse import quote

from django.utils.module_loading import import_string
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

PAR_SOURCE = 6


def _attr(objet, chemin):
    for nom in chemin.split("."):
        objet = getattr(objet, nom, None)
        if objet is None:
            return ""
    return str(objet)


def _tiers(t, mot):
    return f"/{'fournisseurs' if t.est_fournisseur and not t.est_client else 'clients'}?recherche={quote(mot)}"


# (titre, vue de liste, champ du titre, champs du détail, adresse de l'écran)
SOURCES = [
    ("Matériels", "apps.technique.api.MaterielViewSet", "code", ["designation", "immatriculation"], "/parc/{id}"),
    ("Ordres de réparation", "apps.technique.api.OrdreReparationViewSet", "numero", ["materiel.code", "description"], "/ordres/{id}"),
    ("Demandes d'achat", "apps.achats.views.DemandeAchatViewSet", "numero", ["equipement_designation", "numero_or"], "/demandes/{id}"),
    ("Demandes liées au budget", "apps.achats.budget_api.DemandeBudgetViewSet", "numero", ["intitule"], "/budget/{id}"),
    ("Bons de commande", "apps.achats.commande_api.BonCommandeViewSet", "numero", ["fournisseur.raison_sociale", "objet"], "/commandes/{id}"),
    ("Bons de réception", "apps.achats.reception_api.BonReceptionViewSet", "numero", ["commande.numero", "numero_livraison"], "/receptions/{id}"),
    ("Factures fournisseurs", "apps.achats.facture_api.FactureViewSet", "numero", ["numero_facture", "commande.numero"], "/factures/{id}"),
    ("Clients et fournisseurs", "apps.referentiels.views.TiersViewSet", "raison_sociale", ["code", "ville"], _tiers),
    ("Demandes de sortie de stock", "apps.stock.demandes_api.DemandeSortieViewSet", "numero", ["numero_or", "materiel", "motif"], "/stock/demandes/{id}"),
    ("Bons de sortie", "apps.stock.api.BonSortieViewSet", "numero", ["numero_or", "materiel"], "/stock/sorties/{id}"),
    ("GO / NO GO", "apps.commercial.opportunite_api.OpportuniteViewSet", "numero", ["nom_affaire", "client.raison_sociale"], "/opportunites/{id}"),
    ("Devis de location", "apps.commercial.api.DevisViewSet", "numero", ["client.raison_sociale", "libelle"], "/devis/{id}"),
    ("Mises à disposition", "apps.exploitation.api.MiseADispositionViewSet", "numero", ["materiel.code", "devis.client.raison_sociale"], "/mises/{id}"),
    ("Relevés de location", "apps.exploitation.api_releve.ReleveViewSet", "numero", ["devis.client.raison_sociale", "numero_facture"], "/releves/{id}"),
    ("Ordres de transport", "apps.transport.api.OrdreTransportViewSet", "numero", ["client.raison_sociale", "origine", "destination"], "/transports/{id}"),
    ("Personnel", "apps.rh.api.SalarieViewSet", "matricule", ["nom", "prenoms"], "/personnel/{id}"),
    ("Congés et absences", "apps.rh.conges_api.DemandeAbsenceViewSet", "numero", ["salarie.nom", "salarie.prenoms"], "/absences/{id}"),
    ("Événements HSE", "apps.hse.api.EvenementViewSet", "numero", ["lieu", "description"], "/hse/{id}"),
    ("Visites de sécurité", "apps.hse.terrain_api.VisiteViewSet", "numero", ["lieu"], "/hse/visites/{id}"),
    ("Interventions", "apps.moyens.api.DemandeInterventionViewSet", "numero", ["objet", "lieu"], "/interventions/{id}"),
]


def _lignes(classe, request):
    """Les lignes trouvées par la vue de liste, ou None si l'utilisateur n'y a pas droit."""
    vue = classe()
    vue.request, vue.action, vue.kwargs, vue.format_kwarg = request, "list", {}, None
    if not all(p.has_permission(request, vue) for p in vue.get_permissions()):
        return None
    return vue.filter_queryset(vue.get_queryset())


class RechercheView(APIView):
    """GET /api/recherche/?search=mot : les premiers résultats de chaque rubrique, avec l'adresse de leur écran."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        mot = (request.query_params.get("search") or "").strip()
        if len(mot) < 2:
            return Response({"groupes": []})
        groupes = []
        for titre, vue, champ, details, adresse in SOURCES:
            lignes = _lignes(import_string(vue), request)
            if lignes is None:
                continue
            trouves = list(lignes[: PAR_SOURCE + 1])
            if not trouves:
                continue
            groupes.append({
                "titre": titre,
                "autres": len(trouves) > PAR_SOURCE,
                "resultats": [{
                    "titre": _attr(o, champ),
                    "detail": " · ".join(filter(None, (_attr(o, d)[:80] for d in details))),
                    "statut": o.get_statut_display() if hasattr(o, "get_statut_display") else "",
                    "chemin": adresse(o, mot) if callable(adresse) else adresse.format(id=o.pk),
                } for o in trouves[:PAR_SOURCE]],
            })
        return Response({"groupes": groupes})
