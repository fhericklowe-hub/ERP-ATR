from rest_framework.test import APITestCase

from apps.core.models import Site, Utilisateur

from .models import Emplacement, Tiers


class ReferentielsTests(APITestCase):
    def setUp(self):
        self.admin = Utilisateur.objects.create_superuser("admin", password="motdepasse-test")
        self.client.force_authenticate(self.admin)

    def test_un_emplacement_par_site(self):
        self.assertEqual(Emplacement.objects.filter(type="SITE").count(), 4)

    def test_creation_tiers_enregistre_l_auteur(self):
        r = self.client.post("/api/tiers/", {"code": "C001", "raison_sociale": "Client Test", "est_client": True})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Tiers.objects.get(code="C001").cree_par, self.admin)

    def test_emplacement_client(self):
        client = Tiers.objects.create(code="C002", raison_sociale="Port", est_client=True)
        r = self.client.post("/api/emplacements/", {"type": "CLIENT", "nom": "Quai 3", "client": client.id})
        self.assertEqual(r.status_code, 201, r.data)

    def test_emplacement_client_sans_client_refuse(self):
        r = self.client.post("/api/emplacements/", {"type": "CLIENT", "nom": "Inconnu"})
        self.assertEqual(r.status_code, 400)

    def test_emplacement_site_avec_client_refuse(self):
        client = Tiers.objects.create(code="C003", raison_sociale="X", est_client=True)
        site = Site.objects.first()
        r = self.client.post("/api/emplacements/", {"type": "SITE", "nom": "Mixte", "site": site.id, "client": client.id})
        self.assertEqual(r.status_code, 400)
