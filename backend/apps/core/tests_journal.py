from unittest import mock

from django.contrib.auth.models import Group
from rest_framework.test import APITestCase

from .models import Site, Trace, Utilisateur
from .roles import ROLE_COMPTES


class JournalTests(APITestCase):
    def setUp(self):
        self.admin = Utilisateur.objects.create_superuser("admin", password="x")
        self.lecteur = Utilisateur.objects.create_user("lecteur", password="x")
        self.lecteur.groups.add(Group.objects.get(name=ROLE_COMPTES))
        self.simple = Utilisateur.objects.create_user("simple", password="x")

    def test_hors_requete_rien_n_est_trace(self):
        Site.objects.create(code="S1", nom="Siège")
        self.assertEqual(Trace.objects.count(), 0)

    def test_creation_et_modification_tracees_avec_le_nom_des_champs(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post("/api/sites/", {"code": "MAR", "nom": "Marcory"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        site = Site.objects.get(code="MAR")
        self.client.patch(f"/api/sites/{site.id}/", {"nom": "Marcory Zone 4", "ville": "Abidjan"}, format="json")
        self.client.patch(f"/api/sites/{site.id}/", {"nom": "Marcory Zone 4"}, format="json")   # rien ne change : rien à tracer
        creation, modif = Trace.objects.order_by("id")
        self.assertEqual((creation.action, creation.utilisateur, creation.objet_libelle), ("CREATION", self.admin, str(site)))
        self.assertEqual(modif.action, "MODIFICATION")
        self.assertEqual(modif.changements["nom"], ["Marcory", "Marcory Zone 4"])
        self.assertEqual(set(modif.changements), {"nom", "ville"})
        self.assertEqual(Trace.objects.count(), 2)

    def test_les_secrets_et_les_donnees_confidentielles_ne_sont_pas_ecrits(self):
        self.client.force_authenticate(self.admin)
        compte = Utilisateur.objects.create_user("cible", password="x")
        self.client.patch(f"/api/comptes/{compte.id}/", {"mot_de_passe": "Ferke-2027-autre"}, format="json")
        trace = Trace.objects.get(modele="core.utilisateur")
        self.assertIsNone(trace.changements["password"])
        self.assertNotIn("Ferke", str(trace.changements))
        site = Site.objects.create(code="SP", nom="San Pedro")
        with mock.patch("apps.core.journal.CONFIDENTIELS", {"core"}):
            self.client.patch(f"/api/sites/{site.id}/", {"nom": "Port"}, format="json")
        self.assertIsNone(Trace.objects.filter(modele="core.site").latest("id").changements["nom"])

    def test_connexion_seule_ne_laisse_pas_de_trace(self):
        Utilisateur.objects.create_user("agent", password="Abidjan-2026-essai")
        r = self.client.post("/api/auth/token/", {"username": "agent", "password": "Abidjan-2026-essai"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Trace.objects.count(), 0)

    def test_lecture_reservee_et_export(self):
        self.client.force_authenticate(self.admin)
        self.client.post("/api/sites/", {"code": "FK", "nom": "Ferké"}, format="json")
        self.client.force_authenticate(self.simple)
        self.assertEqual(self.client.get("/api/journal/").status_code, 403)
        self.client.force_authenticate(self.lecteur)
        r = self.client.get("/api/journal/?modele=core.site")
        self.assertEqual(r.status_code, 200)
        ligne = r.data["results"][0]
        self.assertEqual((ligne["utilisateur_nom"], ligne["action_libelle"], ligne["objet_libelle"]), ("admin", "Création", str(Site.objects.get(code="FK"))))
        self.assertEqual(self.client.get("/api/journal/?modele=core.service").data["count"], 0)
        self.assertEqual(self.client.get("/api/journal/exporter/").status_code, 200)
        self.assertIn(self.client.delete(f"/api/journal/{ligne['id']}/").status_code, (403, 405))
        self.assertIn(self.client.post("/api/journal/", {}, format="json").status_code, (403, 405))
