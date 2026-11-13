from django.contrib.auth.models import Group
from django.core.management import call_command
from rest_framework.test import APITestCase

from apps.core.models import Utilisateur
from apps.technique.models import Materiel


class PilotageTests(APITestCase):
    def test_reserve_a_la_direction_et_chiffres_coherents(self):
        call_command("donnees_demo", verbosity=0)
        self.assertEqual(self.client.get("/api/pilotage/").status_code, 401)
        self.client.force_authenticate(Utilisateur.objects.get(username="chef"))
        self.assertEqual(self.client.get("/api/pilotage/").status_code, 403)
        direction = Utilisateur.objects.create_user("dg", password="x")
        direction.groups.add(Group.objects.get(name="Direction - Tableau de bord"))
        self.client.force_authenticate(direction)
        Materiel.objects.filter(code="DEMO-CH02").update(etat="EN_PANNE")
        r = self.client.get("/api/pilotage/")
        self.assertEqual(r.status_code, 200)
        modules = {m["module"]: {i["libelle"]: i for i in m["indicateurs"]} for m in r.data}
        self.assertEqual(list(modules), ["Achats", "Stock", "Technique", "Commercial et Exploitation", "Personnel", "HSE", "Moyens généraux"])
        # stock de démonstration : 12×8500 + 3×6200 + 400×2100 + 25×4800 + 4×95000 + 60×2500
        self.assertEqual(modules["Stock"]["Valeur du stock (coût moyen)"]["valeur"], "1 610 600 FCFA")
        self.assertEqual(modules["Stock"]["Articles en stock"]["valeur"], "6")
        panne = modules["Technique"]["En panne ou en réparation"]
        self.assertEqual((panne["valeur"], panne["alerte"]), ("1 (20 %)", True))
        self.assertEqual(modules["Personnel"]["Salariés en poste"]["valeur"], "7")
        self.assertEqual(modules["Achats"]["Commandé ce mois (TTC)"]["valeur"], "0 FCFA")
        self.assertEqual(modules["HSE"]["Jours sans accident avec arrêt"]["valeur"], "aucun accident enregistré")
        # la direction lit le tableau de bord mais n'entre pas dans les dossiers
        self.assertEqual(self.client.get("/api/rh/salaries/").status_code, 403)
