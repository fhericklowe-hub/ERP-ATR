import shutil
import tempfile

from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.core.models import PieceJointe, Service, Site, Utilisateur
from apps.moyens.models import Bien, DemandeIntervention

URL = "/api/pieces-jointes/"
MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA)
class PiecesJointesTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        def utilisateur(nom, role):
            u = Utilisateur.objects.create_user(nom, password="x")
            u.groups.add(Group.objects.get(name=role))
            return u

        self.demandeur = utilisateur("salarie", "Moyens généraux - Demandeur")
        self.autre = utilisateur("autre", "Moyens généraux - Demandeur")
        self.gestionnaire = utilisateur("gestion", "Moyens généraux - Gestionnaire")
        self.sans_role = Utilisateur.objects.create_user("visiteur", password="x")
        site = Site.objects.get(code="MARCORY")
        self.demande = DemandeIntervention.objects.create(
            demandeur=self.demandeur, service=Service.objects.get(code="COM"), site=site, categorie="PLOMBERIE", objet="Fuite")
        self.bien = Bien.objects.create(categorie="MOBILIER", designation="Armoire", site=site)
        self.cible = {"modele": "moyens.demandeintervention", "objet": self.demande.id}

    def joindre(self, par, nom="devis.pdf", contenu=b"%PDF-1.4 essai", **champs):
        self.client.force_authenticate(par)
        donnees = {**self.cible, "fichier": SimpleUploadedFile(nom, contenu), **champs}
        return self.client.post(URL, donnees, format="multipart")

    def lister(self, par, **cible):
        self.client.force_authenticate(par)
        return self.client.get(URL, cible or self.cible)

    def test_joindre_lister_ouvrir(self):
        r = self.joindre(self.demandeur, libelle="Devis du plombier")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data["nom"], r.data["libelle"], r.data["taille"]), ("devis.pdf", "Devis du plombier", 14))
        piece = PieceJointe.objects.get()
        self.assertRegex(piece.fichier.name, r"^pieces/[0-9a-f]{32}\.pdf$")
        liste = self.lister(self.gestionnaire)
        self.assertTrue(liste.data["peut_ajouter"])
        self.assertEqual([p["id"] for p in liste.data["results"]], [piece.id])
        self.assertFalse(liste.data["results"][0]["supprimable"])
        fichier = self.client.get(f"{URL}{piece.id}/telecharger/")
        self.assertEqual(fichier.status_code, 200)
        self.assertEqual(fichier["Content-Type"], "application/pdf")
        self.assertEqual(b"".join(fichier.streaming_content), b"%PDF-1.4 essai")

    def test_droits_du_document(self):
        piece_id = self.joindre(self.demandeur).data["id"]
        # Un collègue qui ne voit pas la demande ne voit ni la liste ni le fichier, et ne peut rien y joindre.
        self.assertEqual(self.lister(self.autre).status_code, 404)
        self.assertEqual(self.client.get(f"{URL}{piece_id}/telecharger/").status_code, 404)
        self.assertEqual(self.joindre(self.autre).status_code, 404)
        self.assertEqual(self.client.delete(f"{URL}{piece_id}/").status_code, 404)
        self.assertEqual(self.lister(self.sans_role).status_code, 404)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(URL, self.cible).status_code, 401)
        self.assertEqual(self.client.get(f"{URL}{piece_id}/telecharger/").status_code, 401)

    def test_lecture_sans_droit_de_modifier(self):
        # Le demandeur voit l'inventaire mais ne le modifie pas : il ne peut pas y joindre de pièce.
        cible = {"modele": "moyens.bien", "objet": self.bien.id}
        self.assertFalse(self.lister(self.demandeur, **cible).data["peut_ajouter"])
        self.assertEqual(self.joindre(self.demandeur, **cible).status_code, 403)
        self.assertEqual(self.joindre(self.gestionnaire, **cible).status_code, 201)

    def test_fichiers_refuses(self):
        self.assertEqual(self.joindre(self.demandeur, nom="outil.exe").status_code, 400)
        self.assertEqual(self.joindre(self.demandeur, nom="page.html").status_code, 400)
        self.assertEqual(self.joindre(self.demandeur, contenu=b"").status_code, 400)
        self.assertEqual(self.joindre(self.demandeur, contenu=b"x" * (10 * 1024 * 1024 + 1)).status_code, 400)
        self.client.force_authenticate(self.demandeur)
        self.assertEqual(self.client.post(URL, self.cible, format="multipart").status_code, 400)
        self.assertFalse(PieceJointe.objects.exists())

    def test_document_inconnu(self):
        for cible in ({"modele": "core.utilisateur", "objet": self.demandeur.id}, {"modele": "moyens.bien", "objet": "abc"},
                      {"modele": "moyens.bien", "objet": 99999}, {}):
            self.client.force_authenticate(self.gestionnaire)
            self.assertEqual(self.client.get(URL, cible).status_code, 404, cible)

    def test_retirer(self):
        piece_id = self.joindre(self.demandeur).data["id"]
        chemin = PieceJointe.objects.get().fichier.path
        self.client.force_authenticate(self.gestionnaire)
        self.assertEqual(self.client.delete(f"{URL}{piece_id}/").status_code, 403)
        self.client.force_authenticate(self.demandeur)
        self.assertEqual(self.client.delete(f"{URL}{piece_id}/").status_code, 204)
        self.assertFalse(PieceJointe.objects.exists())
        import os
        self.assertFalse(os.path.exists(chemin))

    def test_fichier_bureautique_en_telechargement(self):
        piece_id = self.joindre(self.demandeur, nom="comparatif.xlsx", contenu=b"PK").data["id"]
        r = self.client.get(f"{URL}{piece_id}/telecharger/")
        self.assertIn("attachment", r["Content-Disposition"])
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")
