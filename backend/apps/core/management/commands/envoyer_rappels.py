"""python manage.py envoyer_rappels [--simuler]"""
from django.core.management.base import BaseCommand

from apps.core import rappels


class Command(BaseCommand):
    help = "Envoie à chacun, par e-mail, ce qui attend son action (échéances, entretiens, stock sous le seuil)."

    def add_arguments(self, parser):
        parser.add_argument("--simuler", action="store_true", help="Montre qui recevrait quoi, sans rien envoyer")

    def handle(self, simuler, **options):
        envoyes = rappels.envoyer(simuler=simuler)
        for utilisateur, nombre in envoyes:
            self.stdout.write(f"{utilisateur.username} : {nombre} point(s)")
            if simuler:
                self.stdout.write(rappels.texte(utilisateur, rappels.composer(utilisateur)) + "\n")
        self.stdout.write(self.style.SUCCESS(f"{len(envoyes)} rappel(s) {'à envoyer' if simuler else 'envoyé(s)'}."))
