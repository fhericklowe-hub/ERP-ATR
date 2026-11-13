import io

from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook
from rest_framework.test import APITestCase

from apps.core.models import Utilisateur

from .models import Tiers

URL = "/api/tiers/"
TITRES = ["Code", "Raison sociale", "N° contribuable", "Téléphone", "E-mail", "Adresse", "Ville"]


def classeur(*lignes, titres=TITRES):
    wb = Workbook()
    wb.active.append(titres)
    for ligne in lignes:
        wb.active.append(list(ligne))
    tampon = io.BytesIO()
    wb.save(tampon)
    return SimpleUploadedFile("tiers.xlsx", tampon.getvalue())


class TiersTests(APITestCase):
    def setUp(self):
        self.acheteur = Utilisateur.objects.create_user("acheteur", password="x")
        self.acheteur.groups.add(Group.objects.get(name="Achats - Acheteur"))
        self.demandeur = Utilisateur.objects.create_user("demandeur", password="x")
        self.demandeur.groups.add(Group.objects.get(name="Achats - Demandeur"))

    def importer(self, fichier, qualite="fournisseur", par=None, simuler=False):
        self.client.force_authenticate(par or self.acheteur)
        return self.client.post(f"{URL}importer/", {"fichier": fichier, "qualite": qualite, **({"simuler": "1"} if simuler else {})},
                                format="multipart")

    def test_fiche_code_automatique_et_pas_de_suppression(self):
        self.client.force_authenticate(self.demandeur)
        self.assertEqual(self.client.post(URL, {"raison_sociale": "X", "est_fournisseur": True}, format="json").status_code, 403)
        self.client.force_authenticate(self.acheteur)
        r = self.client.post(URL, {"raison_sociale": "Quincaillerie Essai", "est_fournisseur": True}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertRegex(r.data["code"], r"^T\d{5}$")
        autre = self.client.post(URL, {"code": "F-12", "raison_sociale": "Autre Essai", "est_fournisseur": True}, format="json")
        self.assertEqual(autre.data["code"], "F-12")
        self.assertEqual(self.client.post(URL, {"code": "f-12", "raison_sociale": "Doublon"}, format="json").status_code, 201)  # casse différente
        self.assertEqual(self.client.post(URL, {"code": "F-12", "raison_sociale": "Doublon"}, format="json").status_code, 400)
        url = f"{URL}{r.data['id']}/"
        self.assertEqual(self.client.patch(url, {"ville": "Abidjan", "actif": False}, format="json").data["actif"], False)
        self.assertEqual(self.client.patch(url, {"code": ""}, format="json").status_code, 400)
        self.assertIn(self.client.delete(url).status_code, (403, 405))
        self.assertEqual(self.client.get(URL, {"search": "quincaillerie"}).data["count"], 1)

    def test_import(self):
        lignes = [(516890.0, "Gaz Industriels Essai", "CC-1", "27 00 00 00", "contact@example.com", "Bd de Marseille", "Abidjan"),
                  ("", "Pneus Essai", "", "", "", "", "San Pedro")]
        self.assertEqual(self.importer(classeur(*lignes), par=self.demandeur).status_code, 403)
        self.assertEqual(self.importer(classeur(*lignes), qualite="").status_code, 400)
        r = self.importer(classeur(*lignes), simuler=True)
        self.assertEqual((r.data["crees"], r.data["ecrit"], Tiers.objects.count()), (2, False, 0))
        r = self.importer(classeur(*lignes))
        self.assertEqual((r.data["crees"], r.data["ecrit"]), (2, True))
        gaz, pneus = Tiers.objects.get(code="516890"), Tiers.objects.get(raison_sociale="Pneus Essai")
        self.assertEqual((gaz.est_fournisseur, gaz.est_client, gaz.email, gaz.ville), (True, False, "contact@example.com", "Abidjan"))
        self.assertRegex(pneus.code, r"^T\d{5}$")
        self.assertEqual(self.importer(classeur(*lignes)).data["inchanges"], 2)
        # le même tiers importé comme client devient les deux ; une case vide ne vide rien
        r = self.importer(classeur(("516890", "Gaz Industriels Essai", "", "", "", "", "")), qualite="client")
        gaz.refresh_from_db()
        self.assertEqual((r.data["modifies"], gaz.est_client, gaz.est_fournisseur, gaz.ville), (1, True, True, "Abidjan"))
        # erreurs : rien n'est écrit
        r = self.importer(classeur(("N1", "Nouveau Essai", "", "", "", "", ""), ("N2", "", "", "", "", "", ""),
                                   ("N3", "Mail Essai", "", "", "pas-un-mail", "", ""), ("N1", "Encore", "", "", "", "", "")))
        erreurs = " ".join(r.data["erreurs"])
        for attendu in ("Ligne 3 : raison sociale manquante", "Ligne 4 : e-mail invalide", "Ligne 5 : N1 figure deux fois"):
            self.assertIn(attendu, erreurs)
        self.assertEqual((r.data["ecrit"], Tiers.objects.count()), (False, 2))
        self.assertEqual(self.importer(classeur(titres=["Code", "Ville"])).status_code, 400)

    def test_contacts_suivent_les_droits_de_la_fiche(self):
        tiers = Tiers.objects.create(code="F-1", raison_sociale="Essai", est_fournisseur=True)
        corps = {"tiers": tiers.id, "nom": "Contact Essai", "fonction": "Commercial", "telephone": "0700000000"}
        self.client.force_authenticate(self.demandeur)
        self.assertEqual(self.client.post("/api/contacts/", corps, format="json").status_code, 403)
        self.client.force_authenticate(self.acheteur)
        r = self.client.post("/api/contacts/", corps, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        url = f"/api/contacts/{r.data['id']}/"
        self.assertEqual(self.client.patch(url, {"fonction": "Directeur"}, format="json").data["fonction"], "Directeur")
        self.assertEqual(self.client.get(f"{URL}{tiers.id}/").data["contacts"][0]["nom"], "Contact Essai")
        self.client.force_authenticate(self.demandeur)
        self.assertEqual(self.client.delete(url).status_code, 403)
        self.client.force_authenticate(self.acheteur)
        self.assertEqual(self.client.delete(url).status_code, 204)

    def test_sites_du_client_tenus_par_qui_modifie_la_fiche(self):
        from apps.core.models import Site

        from .models import Emplacement
        client = Tiers.objects.create(code="C-1", raison_sociale="Client Essai", est_client=True)
        corps = {"type": "CLIENT", "client": client.id, "nom": "Chantier Essai", "ville": "San Pedro"}
        self.client.force_authenticate(self.demandeur)
        self.assertEqual(self.client.post("/api/emplacements/", corps, format="json").status_code, 403)
        self.client.force_authenticate(self.acheteur)   # modifie les tiers, sans droit sur les emplacements
        r = self.client.post("/api/emplacements/", corps, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        url = f"/api/emplacements/{r.data['id']}/"
        self.assertEqual(self.client.patch(url, {"actif": False}, format="json").data["actif"], False)
        self.assertEqual(self.client.get(f"{URL}{client.id}/").data["sites"][0]["nom"], "Chantier Essai")
        self.assertIn(self.client.delete(url).status_code, (403, 405))
        # Les sites de l'entreprise restent hors de portée : ni création, ni modification, ni changement de type.
        site = Site.objects.first() or Site.objects.create(code="S", nom="Siège")
        self.assertEqual(self.client.post("/api/emplacements/", {"type": "SITE", "site": site.id, "nom": "Magasin"}, format="json").status_code, 403)
        magasin = Emplacement.objects.create(type="SITE", site=site, nom="Magasin Essai")
        self.assertEqual(self.client.patch(f"/api/emplacements/{magasin.id}/", {"nom": "X"}, format="json").status_code, 403)
        self.assertEqual(self.client.patch(url, {"type": "SITE", "site": site.id, "client": None}, format="json").status_code, 403)

    def test_export_excel_des_tiers_et_des_articles(self):
        import io

        from openpyxl import load_workbook
        self.importer(classeur(["F-1", "Pneus Essai", "", "0700000001", "", "", "San Pedro"], ["", "Autre Essai", "", "", "", "", "Ferké"]))
        self.client.force_authenticate(self.acheteur)
        r = self.client.get(f"{URL}exporter/?est_fournisseur=true&search=Pneus")
        self.assertEqual(r.status_code, 200)
        lignes = list(load_workbook(io.BytesIO(r.content)).active.iter_rows(values_only=True))
        self.assertEqual(len(lignes), 2)
        champs = dict(zip(*lignes))
        self.assertEqual((champs["Code"], champs["Raison sociale"], champs["Fournisseur"], champs["Client"], champs["Actif"]),
                         ("F-1", "Pneus Essai", "Oui", "Non", "Oui"))
        self.client.force_authenticate(self.demandeur)   # peut lire les articles, pas les tiers
        self.assertEqual(self.client.get("/api/articles/exporter/").status_code, 200)
        self.assertEqual(self.client.get(f"{URL}exporter/").status_code, 403)
