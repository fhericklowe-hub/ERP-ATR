import datetime
import io
from decimal import Decimal

from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook
from rest_framework.test import APITestCase

from apps.core.models import Utilisateur

from .models import Salarie

URL = "/api/rh/salaries/importer/"
TITRES = ["Matricule", "Nom", "Prénoms", "Sexe", "Date de naissance", "Site", "Service", "Fonction", "Catégorie", "Date d'embauche",
          "Téléphone", "E-mail", "Solde de congés"]


def classeur(*lignes, titres=TITRES):
    wb = Workbook()
    wb.active.append(titres)
    for ligne in lignes:
        wb.active.append(list(ligne))
    tampon = io.BytesIO()
    wb.save(tampon)
    return SimpleUploadedFile("personnel.xlsx", tampon.getvalue())


class ImportPersonnelTests(APITestCase):
    def setUp(self):
        self.rh = Utilisateur.objects.create_user("rh", password="x")
        self.rh.groups.add(Group.objects.get(name="RH - Gestionnaire"))
        self.lecteur = Utilisateur.objects.create_user("lecteur", password="x")
        self.lecteur.groups.add(Group.objects.get(name="RH - Consultation"))

    def importer(self, fichier, par=None, simuler=False):
        self.client.force_authenticate(par or self.rh)
        return self.client.post(URL, {"fichier": fichier, **({"simuler": "1"} if simuler else {})}, format="multipart")

    def test_creation_mise_a_jour_et_simulation(self):
        lignes = [
            ("M100", "Alpha", "Jean", "M", datetime.date(1985, 3, 2), "Siège", "Technique", "Mécanicien", "Ouvrier", "15/01/2020", "0700000000", "", 12.5),
            ("", "Beta", "Awa", "Mme", "", "SAN PEDRO", "", "Assistante", "Employé", "", "", "awa@example.com", ""),
        ]
        self.assertEqual(self.importer(classeur(*lignes), par=self.lecteur).status_code, 403)
        r = self.importer(classeur(*lignes), simuler=True)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data["lues"], r.data["crees"], r.data["ecrit"], Salarie.objects.count()), (2, 2, False, 0))
        r = self.importer(classeur(*lignes))
        self.assertEqual((r.data["crees"], r.data["ecrit"]), (2, True))
        alpha, beta = Salarie.objects.get(matricule="M100"), Salarie.objects.get(nom="BETA")
        self.assertEqual((alpha.sexe, alpha.site.nom, alpha.service.nom, alpha.categorie, alpha.date_embauche, alpha.conges_solde_depart),
                         ("M", "Siège", "Technique", "OUVRIER", datetime.date(2020, 1, 15), Decimal("12.5")))
        self.assertEqual((beta.sexe, beta.site.nom, beta.email, bool(beta.matricule)), ("F", "San Pedro", "awa@example.com", True))
        # relancer le même fichier ne change rien ; une case vide ne vide pas le dossier
        r = self.importer(classeur(*lignes))
        self.assertEqual((r.data["crees"], r.data["modifies"], r.data["inchanges"]), (0, 0, 2))
        r = self.importer(classeur(("M100", "Alpha", "Jean", "", "", "Marcory", "", "Chef d'équipe", "", "", "", "", "")))
        self.assertEqual(r.data["modifies"], 1)
        alpha.refresh_from_db()
        self.assertEqual((alpha.site.nom, alpha.fonction, alpha.telephone, alpha.categorie), ("Marcory", "Chef d'équipe", "0700000000", "OUVRIER"))

    def test_erreurs_signalees_et_rien_n_est_ecrit(self):
        r = self.importer(classeur(
            ("M1", "Bon", "Dossier", "", "", "Siège", "", "", "", "", "", "", ""),
            ("M2", "Sans", "Site", "", "", "", "", "", "", "", "", "", ""),
            ("M3", "Site", "Inconnu", "", "", "Bouaké", "", "", "", "", "", "", ""),
            ("M4", "Mauvaise", "Date", "", "31/02/1990", "Siège", "", "", "", "", "", "", ""),
            ("M5", "Mauvais", "Mail", "", "", "Siège", "", "", "Stagiaire", "", "", "pas-un-mail", ""),
            ("M1", "Double", "Matricule", "", "", "Siège", "", "", "", "", "", "", ""),
            ("M6", "", "Sansnom", "", "", "Siège", "", "", "", "", "", "", ""),
            ("M7", "Embauche", "Avant", "", "01/01/2000", "Siège", "", "", "", "01/01/1999", "", "", ""),
        ))
        self.assertEqual(r.status_code, 200)
        erreurs = " ".join(r.data["erreurs"])
        for attendu in ("Ligne 3 : site manquant", "Ligne 4 : site inconnu", "Ligne 5 : date de naissance illisible", "Ligne 6 : catégorie inconnue",
                        "Ligne 7 : M1 figure deux fois", "Ligne 8 : nom ou prénoms manquant", "Ligne 9 : L'embauche ne peut pas précéder"):
            self.assertIn(attendu, erreurs)
        self.assertEqual((r.data["ecrit"], Salarie.objects.count()), (False, 0))
        self.assertEqual(self.importer(SimpleUploadedFile("x.xlsx", b"pas un classeur")).status_code, 400)
        self.assertEqual(self.importer(classeur(titres=["Matricule", "Site"])).status_code, 400)
        self.client.force_authenticate(self.rh)
        self.assertEqual(self.client.post(URL, {}, format="multipart").status_code, 400)
