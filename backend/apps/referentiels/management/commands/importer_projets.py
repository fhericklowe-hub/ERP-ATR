"""Charge les projets et codes analytiques depuis la feuille « Liste_FG » du classeur des demandes d'achat.
Les noms de clients ne sont pas dans le code de l'application : ils viennent du fichier de l'entreprise."""
from django.core.management.base import BaseCommand, CommandError
from openpyxl import load_workbook

from apps.referentiels.models import Projet


class Command(BaseCommand):
    help = "Importe les projets (type, activité, n° de projet, client, code analytique) d'un classeur Excel."

    def add_arguments(self, parser):
        parser.add_argument("fichier")
        parser.add_argument("--feuille", default="Liste_FG")

    def handle(self, fichier, feuille, **options):
        classeur = load_workbook(fichier, data_only=True, read_only=True)
        if feuille not in classeur.sheetnames:
            raise CommandError(f"Feuille « {feuille} » introuvable. Feuilles : {', '.join(classeur.sheetnames)}")
        lignes = classeur[feuille].iter_rows(values_only=True)
        entetes = [str(c or "").strip().lower() for c in next(lignes)]
        try:
            col = {nom: entetes.index(nom) for nom in ["type", "activité", "n° projet", "client", "code analytique"]}
        except ValueError as e:
            raise CommandError(f"Colonne manquante dans la feuille : {e}")
        crees = 0
        for ligne in lignes:
            numero, nom, code = ligne[col["n° projet"]], ligne[col["client"]], ligne[col["code analytique"]]
            if not (numero and nom and code):
                continue
            _, cree = Projet.objects.update_or_create(
                numero=int(numero), nom=str(nom).strip(),
                defaults={"code_analytique": str(code).strip(), "activite": str(ligne[col["activité"]] or "").strip().title(),
                          "type": str(ligne[col["type"]] or "").strip().upper()},
            )
            crees += cree
        self.stdout.write(self.style.SUCCESS(f"{Projet.objects.count()} projets, dont {crees} nouveaux."))
