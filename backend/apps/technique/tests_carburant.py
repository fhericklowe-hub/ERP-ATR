import datetime
from decimal import Decimal

from django.contrib.auth.models import Group
from rest_framework.test import APITestCase

from apps.core.models import Site, Utilisateur

from .models import Materiel

URL = "/api/technique/pleins/"


class PleinsTests(APITestCase):
    def setUp(self):
        def utilisateur(nom, role):
            u = Utilisateur.objects.create_user(nom, password="x")
            u.groups.add(Group.objects.get(name=role))
            return u

        self.chef = utilisateur("chef", "Technique - Chef d'atelier")
        self.agent = utilisateur("agent", "Transport - Agent")
        self.lecteur = utilisateur("lecteur", "Technique - Consultation")
        self.etranger = utilisateur("etranger", "Achats - Demandeur")
        site = Site.objects.get(code="SIEGE")
        self.tracteur = Materiel.objects.create(code="TR-1", type="TRACTEUR", designation="Tracteur", site=site, compteur_km=50000)
        self.chariot = Materiel.objects.create(code="CH-1", type="CHARIOT", designation="Chariot", site=site)

    def plein(self, par, **champs):
        self.client.force_authenticate(par)
        return self.client.post(URL, {"materiel": self.tracteur.id, "litres": "100", **champs}, format="json")

    def test_saisie_et_consommation(self):
        self.assertEqual(self.plein(self.lecteur).status_code, 403)
        self.assertEqual(self.plein(self.etranger).status_code, 403)
        self.assertEqual(self.plein(self.agent, litres="0").status_code, 400)
        demain = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        self.assertEqual(self.plein(self.agent, date=demain).status_code, 400)
        r = self.plein(self.agent, date="2026-03-01", compteur_km=50200, montant="70000", conducteur="Chauffeur Essai")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self.plein(self.agent, date="2026-03-05", compteur_km=50700, litres="150").status_code, 201)
        self.assertEqual(self.plein(self.agent, date="2026-03-09", compteur_km=51200, litres="160").status_code, 201)
        self.assertEqual(self.plein(self.chef, materiel=self.chariot.id, date="2026-03-02", compteur_heures="1200", litres="40").status_code, 201)
        self.assertEqual(self.plein(self.chef, materiel=self.chariot.id, date="2026-03-08", compteur_heures="1220", litres="50").status_code, 201)
        self.tracteur.refresh_from_db()
        self.assertEqual(self.tracteur.compteur_km, 51200)               # le compteur de la fiche suit
        # seul le chef d'atelier corrige
        self.client.force_authenticate(self.agent)
        self.assertEqual(self.client.patch(f"{URL}{r.data['id']}/", {"litres": "110"}, format="json").status_code, 403)
        self.client.force_authenticate(self.chef)
        self.assertEqual(self.client.patch(f"{URL}{r.data['id']}/", {"litres": "110"}, format="json").status_code, 200)
        self.assertEqual(self.client.patch(f"{URL}{r.data['id']}/", {"materiel": self.chariot.id}, format="json").status_code, 400)
        self.assertIn(self.client.delete(f"{URL}{r.data['id']}/").status_code, (403, 405))
        self.client.force_authenticate(self.lecteur)
        s = self.client.get(f"{URL}synthese/", {"debut": "2026-03-01", "fin": "2026-03-31"}).data
        lignes = {l["code"]: l for l in s["lignes"]}
        # tracteur : 1000 km entre le premier et le dernier compteur, avec 150 + 160 l pris après le premier plein
        self.assertEqual((lignes["TR-1"]["pleins"], lignes["TR-1"]["litres"], lignes["TR-1"]["km"], str(lignes["TR-1"]["consommation_100km"])),
                         (3, Decimal("420.0"), 1000, "31.0"))
        self.assertEqual((lignes["CH-1"]["heures"], str(lignes["CH-1"]["consommation_heure"])), (Decimal("20.0"), "2.5"))   # 50 l / 20 h
        self.assertEqual((s["total"]["pleins"], s["total"]["montant"]), (5, Decimal("70000.00")))
        self.assertEqual(self.client.get(URL, {"materiel": self.chariot.id}).data["count"], 2)
        self.assertEqual(self.client.get(f"{URL}exporter/").status_code, 200)
