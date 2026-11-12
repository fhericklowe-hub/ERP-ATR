from django.contrib.auth.models import Permission
from rest_framework.test import APITestCase

from .models import Site, Utilisateur


class SocleTests(APITestCase):
    def setUp(self):
        self.user = Utilisateur.objects.create_user("awa", password="motdepasse-test")

    def test_sites_initiaux(self):
        self.assertEqual(Site.objects.count(), 4)
        self.assertEqual(Site.objects.get(est_siege=True).code, "SIEGE")

    def test_connexion_par_jeton_et_profil(self):
        r = self.client.post("/api/auth/token/", {"username": "awa", "password": "motdepasse-test"})
        self.assertEqual(r.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        r = self.client.get("/api/moi/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["username"], "awa")

    def test_acces_refuse_sans_connexion(self):
        self.assertEqual(self.client.get("/api/sites/").status_code, 401)

    def test_lecture_exige_le_droit_voir(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get("/api/sites/").status_code, 403)
        self.user.user_permissions.add(Permission.objects.get(codename="view_site"))
        self.user = Utilisateur.objects.get(pk=self.user.pk)
        self.client.force_authenticate(self.user)
        r = self.client.get("/api/sites/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 4)
