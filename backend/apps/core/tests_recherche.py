from django.contrib.auth.models import Group
from django.core.management import call_command
from rest_framework.test import APITestCase

from apps.core.models import Utilisateur
from apps.rh.models import Salarie


class RechercheTests(APITestCase):
    def test_resultats_limites_aux_droits_de_l_utilisateur(self):
        call_command("donnees_demo", verbosity=0)
        self.assertEqual(self.client.get("/api/recherche/?search=demo").status_code, 401)
        admin = Utilisateur.objects.create_superuser("racine", password="x")
        self.client.force_authenticate(admin)
        self.assertEqual(self.client.get("/api/recherche/?search=d").data, {"groupes": []})
        r = self.client.get("/api/recherche/?search=DEMO-CH02")
        self.assertEqual(r.status_code, 200)
        materiels = next(g for g in r.data["groupes"] if g["titre"] == "Matériels")
        self.assertEqual(materiels["resultats"][0]["titre"], "DEMO-CH02")
        self.assertRegex(materiels["resultats"][0]["chemin"], r"^/parc/\d+$")
        # un salarié se trouve par son nom, mais seulement pour qui a accès aux dossiers du personnel
        nom = Salarie.objects.first().nom
        titres = [g["titre"] for g in self.client.get(f"/api/recherche/?search={nom}").data["groupes"]]
        self.assertIn("Personnel", titres)
        direction = Utilisateur.objects.create_user("dg", password="x")
        direction.groups.add(Group.objects.get(name="Direction - Tableau de bord"))
        self.client.force_authenticate(direction)
        self.assertEqual(self.client.get(f"/api/recherche/?search={nom}").data, {"groupes": []})
        self.assertEqual(self.client.get("/api/recherche/?search=DEMO-CH02").data, {"groupes": []})
