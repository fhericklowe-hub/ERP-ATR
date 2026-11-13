from django.contrib.auth.models import Group
from rest_framework.test import APITestCase

from apps.core.models import Utilisateur

from .models import Article, Unite

URL = "/api/articles/"


class CatalogueTests(APITestCase):
    def setUp(self):
        self.unite = Unite.objects.first() or Unite.objects.create(code="U", nom="Unité")
        self.comptes = {}
        for nom, role in [("responsable", "Stock - Responsable"), ("acheteur", "Achats - Acheteur"), ("magasinier", "Stock - Magasinier")]:
            self.comptes[nom] = Utilisateur.objects.create_user(nom, password="x")
            self.comptes[nom].groups.add(Group.objects.get(name=role))

    def test_catalogue_tenu_par_le_responsable_du_stock_et_les_acheteurs(self):
        corps = {"code": "FLT-001", "designation": "Filtre à huile", "nature": "PIECE", "unite": self.unite.id}
        self.client.force_authenticate(self.comptes["magasinier"])
        self.assertEqual(self.client.post(URL, corps, format="json").status_code, 403)
        self.assertEqual(self.client.get(URL).status_code, 200)
        self.client.force_authenticate(self.comptes["responsable"])
        r = self.client.post(URL, corps, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data["nature_libelle"], r.data["unite_code"], r.data["famille_nom"]), ("Pièce détachée", self.unite.code, ""))
        self.assertTrue(Article.objects.get(code="FLT-001").cree_par_id)
        self.assertEqual(self.client.get("/api/familles-articles/").status_code, 200)
        # Même code à la casse près : refusé, comme à l'import du stock.
        self.assertEqual(self.client.post(URL, {**corps, "code": "flt-001"}, format="json").status_code, 400)
        self.client.force_authenticate(self.comptes["acheteur"])
        url = f"{URL}{r.data['id']}/"
        modifie = self.client.patch(url, {"designation": "Filtre à huile moteur", "actif": False, "code": "FLT-001"}, format="json")
        self.assertEqual((modifie.status_code, modifie.data["actif"]), (200, False))
        self.assertIn(self.client.delete(url).status_code, (403, 405))
        self.assertEqual(self.client.get(f"{URL}?actif=true&search=FLT").data["count"], 0)
