"""Quelques documents en cours pour la démonstration, créés par les écrans eux-mêmes (l'API), chacun par son acteur :
ainsi les circuits, les numéros et les contrôles sont ceux de l'application. Tout est fictif."""
import datetime

from django.core.management.base import CommandError
from django.utils import timezone
from rest_framework.test import APIClient


def jouer(comptes, siege, service_technique):
    from apps.referentiels.models import Article, Emplacement, Tiers, Unite
    from apps.stock.models import ReglageStock
    from apps.technique.models import Materiel

    client = APIClient(HTTP_HOST="localhost")
    aujourd_hui = timezone.localdate()

    def envoyer(qui, adresse, **corps):
        client.force_authenticate(comptes[qui])
        reponse = client.post(f"/api/{adresse}", corps, format="json")
        if reponse.status_code >= 300:
            raise CommandError(f"Scénario de démonstration : {adresse} a répondu {reponse.status_code} : {getattr(reponse, 'data', '')}")
        return reponse.data

    unite = Unite.objects.get(code="U").id
    fournisseur = Tiers.objects.get(code="F-DEMO1")
    chariot, grue = Materiel.objects.get(code="DEMO-CH02"), Materiel.objects.get(code="DEMO-GR01")

    # Achats : une demande qui attend le chef d'atelier, et une autre allée jusqu'au bon de commande à valider.
    def demande(*lignes):
        return envoyer("mecanicien", "achats/demandes/", service=service_technique.id, site=siege.id, urgence=2,
                       lignes=[{"designation": d, "quantite": str(q), "unite": unite} for d, q in lignes])

    attente = demande(("Batterie 12 V 100 Ah", 2))
    envoyer("mecanicien", f"achats/demandes/{attente['id']}/soumettre/")
    validee = demande(("Flexible hydraulique 1/2 pouce, 3 m", 4), ("Raccord hydraulique 1/2 pouce", 8))
    envoyer("mecanicien", f"achats/demandes/{validee['id']}/soumettre/")
    envoyer("chef", f"achats/demandes/{validee['id']}/valider/")
    envoyer("responsable", f"achats/demandes/{validee['id']}/valider/")
    bon = envoyer("acheteur", "achats/bons-commande/", demande=validee["id"], fournisseur=fournisseur.id, site=siege.id,
                  service=service_technique.id, objet="Flexibles et raccords hydrauliques", lignes=[
                      {"designation": "Flexible hydraulique 1/2 pouce, 3 m", "quantite": "4", "prix_unitaire": "18500"},
                      {"designation": "Raccord hydraulique 1/2 pouce", "quantite": "8", "prix_unitaire": "3200"}])
    envoyer("acheteur", f"achats/bons-commande/{bon['id']}/soumettre/")

    # Stock : un article passe sous son seuil d'alerte.
    magasin = Emplacement.objects.filter(type="SITE", site=siege).first()
    ReglageStock.objects.get_or_create(article=Article.objects.get(code="DEMO-FILTRE-G"), magasin=magasin, defaults={"seuil_mini": 5})

    # Technique : un chariot en panne, avec son ordre de réparation.
    envoyer("mecanicien", "technique/ordres/", materiel=chariot.id, description="Fuite hydraulique au mât, levage impossible")

    # Commercial : un devis de location envoyé au client.
    devis = envoyer("commercial", "commercial/devis/", client=Tiers.objects.get(code="C-DEMO1").id, site=siege.id,
                    libelle="Location d'une grue mobile 50 t avec opérateur", type_loyer="JOUR", echeance="30 JOURS NETS",
                    mode_reglement="CHEQUE", lignes=[{"designation": "Grue mobile 50 t avec opérateur", "materiel": grue.id,
                                                      "quantite": "1", "prix_unitaire": "450000", "duree": "5"}])
    envoyer("commercial", f"commercial/devis/{devis['id']}/envoyer/")

    # HSE : un presqu'accident à analyser, et une visite de sécurité avec une action en cours.
    envoyer("mecanicien", "hse/evenements/", type="PRESQUE", site=siege.id, lieu="Atelier, zone de levage",
            date=(timezone.now() - datetime.timedelta(hours=3)).isoformat(),
            description="Une élingue a glissé pendant la dépose d'un mât. Personne dans la zone.", mesures_immediates="Zone balisée.")
    visite = envoyer("chef", "hse/visites/", site=siege.id, lieu="Parc engins, zone de lavage",
                     points_positifs="Cales posées sous les engins à l'arrêt.", ecarts="Extincteur masqué par des palettes.")
    envoyer("chef", "hse/actions/", visite=visite["id"], description="Dégager l'accès à l'extincteur",
            responsable=comptes["mecanicien"].id, echeance=str(aujourd_hui + datetime.timedelta(days=3)))

    # EPI : des chaussures de sécurité à renouveler bientôt.
    client.force_authenticate(comptes["responsable"])
    mecanicien = next(s for s in client.get("/api/hse/epi/salaries/").data if "MÉCANICIEN" in s["nom"].upper())
    envoyer("responsable", "hse/epi/", salarie=mecanicien["id"], equipement="CHAUSSURES", precision="Pointure 43",
            date_remise=str(aujourd_hui - datetime.timedelta(days=350)), a_renouveler_le=str(aujourd_hui + datetime.timedelta(days=10)))
