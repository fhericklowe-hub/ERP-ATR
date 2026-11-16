import datetime
from decimal import Decimal

from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.core.models import Site, Utilisateur
from apps.referentiels.models import Tiers
from apps.technique.models import Materiel

from .models import OrdreTransport

URL = "/api/transport/ordres/"


class OrdreTransportTests(APITestCase):
    def setUp(self):
        def utilisateur(nom, role):
            u = Utilisateur.objects.create_user(nom, password="x")
            u.groups.add(Group.objects.get(name=role))
            return u

        self.agent = utilisateur("agent", "Transport - Agent")
        self.lecteur = utilisateur("lecteur", "Transport - Consultation")
        self.etranger = utilisateur("etranger", "Achats - Demandeur")
        self.site = Site.objects.get(code="SIEGE")
        self.client_a = Tiers.objects.create(code="C1", raison_sociale="Client Essai", est_client=True)
        self.tracteur = Materiel.objects.create(code="TR-1", type="TRACTEUR", designation="Tracteur 6x4", site=self.site, compteur_km=100000)
        self.remorque = Materiel.objects.create(code="RQ-1", type="REMORQUE", designation="Plateau 40 pieds", site=self.site)
        self.chariot = Materiel.objects.create(code="CH-1", type="CHARIOT", designation="Chariot", site=self.site)

    def corps(self, **champs):
        return {"client": self.client_a.id, "site": self.site.id, "origine": "Port d'Abidjan", "destination": "Ferké",
                "date_prevue": timezone.localdate().isoformat(), "tracteur": self.tracteur.id, "remorque": self.remorque.id,
                "chauffeur": "Chauffeur Essai", **champs}

    def creer(self, **champs):
        self.client.force_authenticate(self.agent)
        return self.client.post(URL, self.corps(**champs), format="json")

    def agir(self, par, id, action, **donnees):
        self.client.force_authenticate(par)
        return self.client.post(f"{URL}{id}/{action}/", donnees, format="json")

    def test_circuit_d_un_ordre(self):
        self.client.force_authenticate(self.lecteur)
        self.assertEqual(self.client.post(URL, self.corps(), format="json").status_code, 403)
        self.assertEqual(self.creer(tracteur=self.chariot.id).status_code, 400)             # pas un tracteur
        self.assertEqual(self.creer(remorque=self.tracteur.id).status_code, 400)            # pas une remorque
        r = self.creer()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertRegex(r.data["numero"], r"^OT-\d{4}-0001$")
        id = r.data["id"]
        self.assertEqual(self.agir(self.lecteur, id, "demarrer", km=100050).status_code, 403)
        self.assertEqual(self.agir(self.agent, id, "demarrer").status_code, 400)             # compteur obligatoire
        self.assertEqual(self.agir(self.agent, id, "demarrer", km=99000).status_code, 400)   # compteur qui recule
        self.assertEqual(self.agir(self.agent, id, "livrer", km=100600).status_code, 400)    # pas encore parti
        r = self.agir(self.agent, id, "demarrer", km=100050)
        self.assertEqual((r.status_code, r.data["statut"], r.data["km_depart"]), (200, "EN_COURS", 100050))
        # le tracteur et la remorque sont pris : un second ordre ne peut pas partir
        autre = self.creer().data["id"]
        self.assertEqual(self.agir(self.agent, autre, "demarrer", km=100050).status_code, 400)
        self.client.force_authenticate(self.agent)
        self.assertEqual(self.client.patch(f"{URL}{id}/", {"chauffeur": "Autre"}, format="json").status_code, 400)   # parti : figé
        self.assertEqual(self.agir(self.agent, id, "livrer", km=100000, litres="200").status_code, 400)
        r = self.agir(self.agent, id, "livrer", km=100650, litres="210", reserves="Bâche déchirée")
        self.assertEqual((r.data["statut"], r.data["km_parcourus"], str(r.data["consommation_100km"]), r.data["reserves"]),
                         ("LIVRE", 600, "35.0", "Bâche déchirée"))
        self.tracteur.refresh_from_db()
        self.assertEqual(self.tracteur.compteur_km, 100650)
        self.assertEqual(self.agir(self.agent, id, "annuler", motif="Trop tard").status_code, 400)
        self.assertEqual(self.agir(self.agent, autre, "annuler", motif="").status_code, 400)
        self.assertEqual(self.agir(self.agent, autre, "annuler", motif="Client a reporté").data["statut"], "ANNULE")
        self.client.force_authenticate(self.agent)
        self.assertIn(self.client.delete(f"{URL}{id}/").status_code, (403, 405))

    def test_tracteur_en_panne_et_synthese(self):
        id = self.creer().data["id"]
        Materiel.objects.filter(pk=self.tracteur.pk).update(etat="EN_PANNE")
        self.assertEqual(self.agir(self.agent, id, "demarrer", km=100010).status_code, 400)
        Materiel.objects.filter(pk=self.tracteur.pk).update(etat="DISPONIBLE")
        for km_depart, km_arrivee, litres in ((100010, 100410, "120"), (100410, 100610, None)):
            id = self.creer().data["id"]
            self.agir(self.agent, id, "demarrer", km=km_depart)
            self.assertEqual(self.agir(self.agent, id, "livrer", km=km_arrivee, litres=litres).status_code, 200)
        self.client.force_authenticate(self.lecteur)
        s = self.client.get(f"{URL}synthese/").data
        tracteur, chauffeur = s["par_tracteur"][0], s["par_chauffeur"][0]
        # 600 km en deux trajets ; la consommation ne porte que sur le trajet où le carburant est saisi : 120 l / 400 km
        self.assertEqual((s["ordres"], tracteur["km"], tracteur["ordres"], str(tracteur["consommation_100km"]), chauffeur["nom"]),
                         (2, 600, 2, "30.0", "Chauffeur Essai"))
        self.assertEqual(self.client.get(f"{URL}exporter/").status_code, 200)
        self.assertEqual(self.client.get(URL, {"statut": "LIVRE"}).data["count"], 2)
        self.client.force_authenticate(self.etranger)
        self.assertEqual(self.client.get(URL).status_code, 403)
        self.assertEqual(OrdreTransport.objects.filter(statut="PLANIFIE").count(), 1)
