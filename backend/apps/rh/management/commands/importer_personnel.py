"""python manage.py importer_personnel personnel.xlsx --utilisateur franck [--simuler]"""
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.core.models import Utilisateur
from apps.rh.imports import importer


class Command(BaseCommand):
    help = "Crée ou met à jour les dossiers du personnel depuis un classeur Excel (colonnes : nom, prénoms, site, matricule...)."

    def add_arguments(self, parser):
        parser.add_argument("fichier")
        parser.add_argument("--utilisateur", required=True, help="Identifiant du gestionnaire RH qui fait l'import")
        parser.add_argument("--simuler", action="store_true", help="Contrôle le fichier sans rien écrire")

    def handle(self, fichier, utilisateur, simuler, **options):
        auteur = Utilisateur.objects.filter(username=utilisateur).first()
        if not auteur:
            raise CommandError("Utilisateur inconnu.")
        try:
            bilan = importer(auteur, fichier, simuler=simuler)
        except (ValidationError, PermissionDenied) as e:
            raise CommandError("; ".join(getattr(e, "messages", [str(e)])))
        for erreur in bilan["erreurs"]:
            self.stderr.write(erreur)
        resume = (f"{bilan['lues']} lignes lues, {bilan['crees']} salariés créés, {bilan['modifies']} modifiés, "
                  f"{bilan['inchanges']} inchangés.")
        self.stdout.write(self.style.SUCCESS(resume) if bilan["ecrit"] else self.style.WARNING(resume + " Rien n'a été écrit."))
