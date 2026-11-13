"""python manage.py donnees_demo [--mot-de-passe ...]

Remplit une base d'essai avec des données FICTIVES pour une démonstration : un compte par profil, quelques
fournisseurs, clients, articles en stock, matériels et salariés. Rien ici ne vient de l'entreprise.
La commande refuse de tourner ailleurs que sur une base SQLite locale, et ne recrée pas ce qui existe déjà."""
import datetime
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.core.models import Service, Site, Utilisateur
from apps.referentiels.models import Article, Emplacement, Tiers, Unite

# identifiant : (prénom, nom, service, rôles). Le compte « responsable » cumule les rôles de pilotage pour tout montrer.
COMPTES = {
    "responsable": ("Démo", "Responsable", "ACHATS", [
        "Achats - Demandeur", "Achats - Responsable achats", "Achats - Directeur technique", "Moyens généraux - Gestionnaire", "Moyens généraux - Demandeur",
        "Stock - Responsable", "Technique - Chef d'atelier", "Commercial - Responsable", "Exploitation - Agent",
        "RH - Gestionnaire", "RH - Salarié", "HSE - Responsable", "Direction - Tableau de bord"]),
    "controleur": ("Démo", "Contrôleur", "FINANCES", ["Achats - Contrôleur de gestion", "RH - Salarié", "HSE - Déclarant"]),
    "acheteur": ("Démo", "Acheteur", "ACHATS", ["Achats - Acheteur", "Achats - Demandeur", "RH - Salarié", "HSE - Déclarant"]),
    "magasinier": ("Démo", "Magasinier", "STOCK", ["Achats - Magasinier", "Stock - Magasinier", "RH - Salarié", "HSE - Déclarant"]),
    "chef": ("Démo", "Chef d'atelier", "TECHNIQUE", [
        "Achats - Demandeur", "Stock - Demandeur", "Technique - Chef d'atelier", "Moyens généraux - Demandeur",
        "RH - Salarié", "HSE - Visiteur"]),
    "mecanicien": ("Démo", "Mécanicien", "TECHNIQUE", [
        "Achats - Demandeur", "Stock - Demandeur", "Technique - Mécanicien", "Moyens généraux - Demandeur",
        "RH - Salarié", "HSE - Déclarant"]),
    "commercial": ("Démo", "Commercial", "COMMERCIAL", ["Commercial - Commercial", "Exploitation - Consultation", "RH - Salarié", "HSE - Déclarant"]),
}
TIERS = [  # code, raison sociale, client, fournisseur
    ("F-DEMO1", "Pièces et Hydraulique Démo", False, True),
    ("F-DEMO2", "Fournitures Générales Démo", False, True),
    ("C-DEMO1", "Client Portuaire Démo", True, False),
    ("C-DEMO2", "Client Chantier Démo", True, False),
]
ARTICLES = [  # code, désignation, unité, quantité, prix unitaire
    ("DEMO-FILTRE-H", "Filtre à huile moteur", "U", 12, 8500),
    ("DEMO-FILTRE-G", "Filtre à gasoil", "U", 3, 6200),
    ("DEMO-HUILE-15W40", "Huile moteur 15W40", "L", 400, 2100),
    ("DEMO-FLEXIBLE", "Flexible hydraulique 1/2 pouce", "M", 25, 4800),
    ("DEMO-PNEU-700", "Pneu chariot 7.00-12", "U", 4, 95000),
    ("DEMO-RAMETTE", "Ramette de papier A4", "U", 60, 2500),
]
MATERIELS = [  # code, type, désignation, site
    ("DEMO-CH01", "CHARIOT", "Chariot élévateur 3,5 t", "Siège"),
    ("DEMO-CH02", "CHARIOT", "Chariot élévateur 7 t", "Marcory"),
    ("DEMO-GR01", "GRUE", "Grue mobile 50 t", "Siège"),
    ("DEMO-NA01", "NACELLE", "Nacelle articulée 16 m", "San Pedro"),
    ("DEMO-CA01", "CAMION", "Camion plateau 19 t", "Ferké"),
]


class Command(BaseCommand):
    help = "Crée des comptes et des données fictives pour une démonstration sur un poste (base SQLite uniquement)."

    def add_arguments(self, parser):
        parser.add_argument("--mot-de-passe", default="demo-atr", help="Mot de passe commun des comptes de démonstration")

    @transaction.atomic
    def handle(self, mot_de_passe, **options):
        if "sqlite" not in settings.DATABASES["default"]["ENGINE"]:
            raise CommandError("Les données de démonstration ne se chargent que sur une base d'essai SQLite, jamais sur le serveur.")
        from apps.achats.models import Acheteur
        from apps.rh.models import Salarie
        from apps.stock.models import ajuster, quantite_en_stock
        from apps.technique.models import Materiel

        siege = Site.objects.filter(est_siege=True).first() or Site.objects.first()
        services = {s.code.upper(): s for s in Service.objects.all()}

        def service(mot):
            return next((s for code, s in services.items() if mot in code or mot in s.nom.upper()), None)

        comptes = {}
        for identifiant, (prenom, nom, mot, roles) in COMPTES.items():
            u, cree = Utilisateur.objects.get_or_create(username=identifiant, defaults={
                "first_name": prenom, "last_name": nom, "site": siege, "service": service(mot), "is_staff": identifiant == "responsable",
                "is_superuser": identifiant == "responsable"})
            if cree:
                u.set_password(mot_de_passe)
                u.save()
            u.groups.add(*Group.objects.filter(name__in=roles))   # à chaque lancement : les rôles ajoutés depuis sont donnés
            comptes[identifiant] = u
        chef, responsable = comptes["chef"], comptes["responsable"]
        Acheteur.objects.get_or_create(utilisateur=comptes["acheteur"])   # sans acheteur, aucune demande n'est attribuée
        for s in Service.objects.filter(responsable__isnull=True):
            s.responsable = chef if s == service("TECHNI") else responsable
            s.save(update_fields=["responsable"])

        for code, raison, client, fournisseur in TIERS:
            Tiers.objects.get_or_create(code=code, defaults={"raison_sociale": raison, "est_client": client, "est_fournisseur": fournisseur,
                                                             "ville": "Abidjan"})
        magasin = Emplacement.objects.filter(type="SITE", site=siege).first()
        for code, designation, unite, quantite, prix in ARTICLES:
            article, _ = Article.objects.get_or_create(code=code, defaults={
                "designation": designation, "unite": Unite.objects.get(code=unite), "gere_en_stock": True})
            if magasin and not quantite_en_stock(article, magasin):
                ajuster(responsable, article, magasin, Decimal(quantite), "Stock de départ de la démonstration", prix_unitaire=Decimal(prix))
        sites = {s.nom: s for s in Site.objects.all()}
        for code, type_, designation, site in MATERIELS:
            Materiel.objects.get_or_create(code=code, defaults={"type": type_, "designation": designation, "site": sites.get(site, siege)})
        embauche = datetime.date(timezone.localdate().year - 3, 1, 15)
        for identifiant, u in comptes.items():
            Salarie.objects.get_or_create(utilisateur=u, defaults={
                "nom": u.last_name.upper(), "prenoms": u.first_name, "site": siege, "service": u.service, "date_embauche": embauche,
                "responsable": None if identifiant in ("responsable", "chef") else Salarie.objects.filter(utilisateur=chef if identifiant == "mecanicien" else responsable).first()})
        self.stdout.write(self.style.SUCCESS(
            f"Données de démonstration prêtes. Comptes : {', '.join(COMPTES)} (mot de passe : {mot_de_passe})."))
