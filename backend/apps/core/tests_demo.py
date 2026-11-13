from django.core.management import call_command
from rest_framework.test import APITestCase

from apps.core.models import Utilisateur


class DonneesDemoTests(APITestCase):
    def test_comptes_et_donnees_fictives(self):
        call_command("donnees_demo", verbosity=0)
        call_command("donnees_demo", verbosity=0)                    # relancer ne duplique rien
        self.assertEqual(Utilisateur.objects.count(), 7)
        r = self.client.post("/api/auth/token/", {"username": "mecanicien", "password": "demo-atr"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.client.force_authenticate(Utilisateur.objects.get(username="responsable"))
        for adresse, minimum in (("/api/stock/valeur/", None), ("/api/technique/materiels/", 5), ("/api/rh/salaries/", 7),
                                 ("/api/hse/epi/salaries/", None), ("/api/tiers/", 4)):
            r = self.client.get(adresse)
            self.assertEqual(r.status_code, 200, adresse)
            if minimum:
                self.assertGreaterEqual(r.data["count"], minimum, adresse)
        # le scénario laisse du travail à chacun, et ne se rejoue pas
        from apps.achats.models import DemandeAchat

        self.assertEqual(DemandeAchat.objects.count(), 2)
        attendus = {"chef": "Demandes d'achat à traiter", "responsable": "Bons de commande à valider", "mecanicien": "Actions correctives HSE"}
        for identifiant, titre in attendus.items():
            self.client.force_authenticate(Utilisateur.objects.get(username=identifiant))
            self.assertIn(titre, [x["titre"] for x in self.client.get("/api/accueil/").data], identifiant)
