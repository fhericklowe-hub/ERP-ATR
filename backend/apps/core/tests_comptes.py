from django.contrib.auth.models import Group
from rest_framework.test import APITestCase

from .models import Utilisateur
from .roles import ROLE_COMPTES

URL = "/api/comptes/"


class ComptesTests(APITestCase):
    def setUp(self):
        self.gestionnaire = Utilisateur.objects.create_user("gestionnaire", password="x")
        self.gestionnaire.groups.add(Group.objects.get(name=ROLE_COMPTES))
        self.simple = Utilisateur.objects.create_user("simple", password="x")
        self.admin = Utilisateur.objects.create_superuser("admin", password="x")

    def test_reserve_au_gestionnaire_des_comptes(self):
        self.client.force_authenticate(self.simple)
        self.assertEqual(self.client.get(URL).status_code, 403)
        self.assertEqual(self.client.post(URL, {"username": "x", "mot_de_passe": "Abidjan-2026-essai"}, format="json").status_code, 403)
        self.assertEqual(self.client.patch(f"{URL}{self.simple.id}/", {"roles": [ROLE_COMPTES]}, format="json").status_code, 403)

    def test_creation_roles_mot_de_passe_desactivation(self):
        self.client.force_authenticate(self.gestionnaire)
        self.assertIn("Achats - Acheteur", self.client.get(f"{URL}roles/").data)
        corps = {"username": "nouveau", "first_name": "Compte", "last_name": "Essai", "roles": ["Achats - Demandeur"]}
        self.assertEqual(self.client.post(URL, corps, format="json").status_code, 400)                              # sans mot de passe
        self.assertEqual(self.client.post(URL, {**corps, "mot_de_passe": "12345678"}, format="json").status_code, 400)  # trop simple
        r = self.client.post(URL, {**corps, "mot_de_passe": "Abidjan-2026-essai"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertNotIn("mot_de_passe", r.data)
        compte = Utilisateur.objects.get(username="nouveau")
        self.assertTrue(compte.check_password("Abidjan-2026-essai"))
        self.assertEqual((compte.is_staff, compte.is_superuser, r.data["roles"]), (False, False, ["Achats - Demandeur"]))
        url = f"{URL}{compte.id}/"
        r = self.client.patch(url, {"roles": ["Achats - Acheteur", "Stock - Magasinier"], "fonction": "Acheteur"}, format="json")
        self.assertEqual(sorted(r.data["roles"]), ["Achats - Acheteur", "Stock - Magasinier"])
        self.assertTrue(Utilisateur.objects.get(pk=compte.pk).check_password("Abidjan-2026-essai"))   # inchangé sans saisie
        self.client.patch(url, {"mot_de_passe": "Ferke-2027-autre"}, format="json")
        self.assertTrue(Utilisateur.objects.get(pk=compte.pk).check_password("Ferke-2027-autre"))
        self.assertEqual(self.client.patch(url, {"username": "autre"}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"roles": ["Inconnu"]}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"is_active": False}, format="json").data["is_active"], False)
        self.assertEqual(self.client.delete(url).status_code, 405)

    def test_garde_fous(self):
        self.client.force_authenticate(self.gestionnaire)
        moi = f"{URL}{self.gestionnaire.id}/"
        self.assertEqual(self.client.patch(moi, {"roles": [ROLE_COMPTES, "Achats - Responsable achats"]}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(moi, {"is_active": False}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(moi, {"telephone": "0700000000"}, format="json").status_code, 200)
        # Le compte d'un administrateur est hors de portée, mot de passe compris.
        r = self.client.patch(f"{URL}{self.admin.id}/", {"mot_de_passe": "Abidjan-2026-essai"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertTrue(Utilisateur.objects.get(pk=self.admin.pk).check_password("x"))
        # On ne fabrique pas un administrateur par cet écran.
        r = self.client.post(URL, {"username": "ruse", "mot_de_passe": "Abidjan-2026-essai", "is_superuser": True, "is_staff": True}, format="json")
        ruse = Utilisateur.objects.get(username="ruse")
        self.assertEqual((r.status_code, ruse.is_superuser, ruse.is_staff), (201, False, False))
