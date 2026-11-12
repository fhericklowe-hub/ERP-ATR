"""python manage.py importer_stock stock.xlsx --magasin SIEGE --utilisateur franck [--simuler]"""
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.core.models import Utilisateur
from apps.referentiels.models import Emplacement
from apps.stock.imports import importer


class Command(BaseCommand):
    help = "Met le stock d'un magasin aux quantités d'un classeur Excel (colonnes : code, désignation, unité, quantité...)."

    def add_arguments(self, parser):
        parser.add_argument("fichier")
        parser.add_argument("--magasin", required=True, help="Code du site (SIEGE, MARCORY...)")
        parser.add_argument("--utilisateur", required=True, help="Identifiant du responsable du stock qui fait l'import")
        parser.add_argument("--simuler", action="store_true", help="Contrôle le fichier sans rien écrire")

    def handle(self, fichier, magasin, utilisateur, simuler, **options):
        lieu = Emplacement.objects.filter(type="SITE", site__code__iexact=magasin).first()
        auteur = Utilisateur.objects.filter(username=utilisateur).first()
        if not lieu or not auteur:
            raise CommandError("Magasin ou utilisateur inconnu.")
        try:
            bilan = importer(auteur, fichier, lieu, simuler=simuler)
        except (ValidationError, PermissionDenied) as e:
            raise CommandError("; ".join(getattr(e, "messages", [str(e)])))
        for erreur in bilan["erreurs"]:
            self.stderr.write(erreur)
        resume = (f"{bilan['lues']} lignes lues, {bilan['articles_crees']} articles créés, "
                  f"{bilan['stocks_modifies']} stocks modifiés, {bilan['inchanges']} inchangés.")
        if bilan["ecrit"]:
            self.stdout.write(self.style.SUCCESS(resume))
        else:
            self.stdout.write(self.style.WARNING(resume + " Rien n'a été écrit."))
