import datetime

from django.contrib.auth.models import Group
from django.core import mail
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.core import rappels
from apps.core.models import Site, Utilisateur
from apps.technique.models import Materiel

from .models import Evenement

EVENEMENTS = "/api/hse/evenements/"
ACTIONS = "/api/hse/actions/"


class EvenementsTests(APITestCase):
    def setUp(self):
        def compte(nom, *roles, **champs):
            u = Utilisateur.objects.create_user(nom, password="x", first_name=nom.capitalize(), **champs)
            u.groups.add(*Group.objects.filter(name__in=roles))
            return u

        self.hse = compte("hse", "HSE - Responsable", email="hse@example.com")
        self.agent = compte("agent", "HSE - Déclarant", email="agent@example.com")
        self.chef = compte("chef", "HSE - Déclarant", email="chef@example.com")
        self.autre = compte("autre", "HSE - Déclarant")
        self.etranger = compte("etranger", "Achats - Demandeur")
        self.site = Site.objects.get(code="SIEGE")
        self.chariot = Materiel.objects.create(code="CH-012", type="CHARIOT", designation="Chariot 3,5 t", site=self.site)
        self.hier = timezone.now() - datetime.timedelta(days=1)

    def declarer(self, par=None, **champs):
        self.client.force_authenticate(par or self.agent)
        return self.client.post(EVENEMENTS, {"type": "PRESQUE", "date": self.hier.isoformat(), "site": self.site.id,
                                             "description": "Une palette a glissé des fourches.", **champs}, format="json")

    def agir(self, par, url, **donnees):
        self.client.force_authenticate(par)
        return self.client.post(url, donnees, format="json")

    def test_declaration_et_visibilite(self):
        r = self.declarer(materiel=self.chariot.id, lieu="Quai 2", mesures_immediates="Zone balisée")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data["statut"], r.data["declarant_nom"], r.data["materiel_nom"], r.data["gravite"]), ("DECLARE", "Agent", str(self.chariot), "1"))
        self.assertRegex(r.data["numero"], r"^HSE-\d{4}-0001$")
        id = r.data["id"]
        self.assertEqual(self.declarer(date=(timezone.now() + datetime.timedelta(days=1)).isoformat()).status_code, 400)
        self.assertEqual(self.declarer(jours_arret=3).status_code, 400)                    # pas un accident
        self.assertEqual(self.declarer(type="ACCIDENT", jours_arret=3, gravite="2").status_code, 201)
        self.assertEqual(self.declarer(par=self.etranger).status_code, 403)
        # l'auteur corrige sa déclaration ; les autres déclarants ne la voient pas
        self.client.force_authenticate(self.agent)
        self.assertEqual(self.client.patch(f"{EVENEMENTS}{id}/", {"lieu": "Quai 3"}, format="json").data["lieu"], "Quai 3")
        self.assertEqual(self.client.get(EVENEMENTS).data["count"], 2)
        self.assertEqual(self.client.get(f"{EVENEMENTS}indicateurs/").status_code, 403)
        self.assertIn(self.client.delete(f"{EVENEMENTS}{id}/").status_code, (403, 405))
        self.client.force_authenticate(self.autre)
        self.assertEqual(self.client.get(EVENEMENTS).data["count"], 0)
        self.assertEqual(self.client.get(f"{EVENEMENTS}{id}/").status_code, 404)
        self.assertEqual(self.client.patch(f"{EVENEMENTS}{id}/", {"lieu": "x"}, format="json").status_code, 404)
        self.client.force_authenticate(self.etranger)
        self.assertEqual(self.client.get(EVENEMENTS).status_code, 403)
        self.client.force_authenticate(self.hse)
        self.assertEqual(self.client.get(EVENEMENTS).data["count"], 2)
        i = self.client.get(f"{EVENEMENTS}indicateurs/").data
        self.assertEqual((i["total"], i["accidents_avec_arret"], i["jours_arret"], i["jours_sans_accident"], i["a_traiter"]), (2, 1, 3, 1, 2))

    def test_analyse_actions_et_cloture(self):
        id = self.declarer().data["id"]
        url = f"{EVENEMENTS}{id}/"
        self.assertEqual(self.agir(self.agent, f"{url}analyser/", causes="x").status_code, 403)
        self.assertEqual(self.agir(self.hse, f"{url}analyser/").status_code, 400)
        self.assertEqual(self.agir(self.hse, f"{url}clore/", conclusion="x").status_code, 400)     # pas d'analyse
        r = self.agir(self.hse, f"{url}analyser/", causes="Palette mal filmée, sol mouillé.", gravite="2")
        self.assertEqual((r.data["statut"], r.data["gravite"]), ("ANALYSE", "2"))
        self.assertEqual(self.agir(self.hse, f"{url}analyser/", causes="x", jours_arret=2).status_code, 400)
        self.client.force_authenticate(self.agent)
        self.assertEqual(self.client.patch(url, {"lieu": "x"}, format="json").status_code, 403)    # figée pour l'auteur
        # actions correctives
        action = {"evenement": id, "description": "Rappeler la consigne de filmage", "responsable": self.chef.id,
                  "echeance": str(timezone.localdate() + datetime.timedelta(days=3))}
        self.assertEqual(self.agir(self.agent, ACTIONS, **action).status_code, 403)
        a1 = self.agir(self.hse, ACTIONS, **action).data
        a2 = self.agir(self.hse, ACTIONS, **{**action, "description": "Poser un tapis antidérapant", "echeance": "2026-01-05"}).data
        self.assertEqual((a1["statut"], a2["en_retard"]), ("A_FAIRE", True))
        # le responsable de l'action voit l'événement et ses actions, et les termine
        self.client.force_authenticate(self.chef)
        self.assertEqual(self.client.get(EVENEMENTS).data["count"], 1)
        self.assertEqual(self.client.get(ACTIONS).data["count"], 2)
        self.assertEqual(self.agir(self.autre, f"{ACTIONS}{a1['id']}/terminer/").status_code, 404)
        rappels.envoyer()
        corps = {m.to[0]: m.body for m in mail.outbox}
        self.assertIn("Rappeler la consigne", corps["chef@example.com"])
        self.assertIn("en retard", corps["chef@example.com"])
        self.assertNotIn("hse@example.com", corps)                                             # plus rien à analyser
        self.assertEqual(self.agir(self.hse, f"{url}clore/", conclusion="Consignes rappelées").status_code, 400)   # actions à faire
        r = self.agir(self.chef, f"{ACTIONS}{a1['id']}/terminer/", commentaire="Fait au quart du matin")
        self.assertEqual((r.data["statut"], r.data["faite_le"]), ("FAITE", str(timezone.localdate())))
        self.assertEqual(self.agir(self.chef, f"{ACTIONS}{a1['id']}/terminer/").status_code, 403)
        self.assertEqual(self.agir(self.chef, f"{ACTIONS}{a2['id']}/abandonner/", commentaire="x").status_code, 403)
        self.assertEqual(self.agir(self.hse, f"{ACTIONS}{a2['id']}/abandonner/").status_code, 400)
        self.assertEqual(self.agir(self.hse, f"{ACTIONS}{a2['id']}/abandonner/", commentaire="Sol refait").data["statut"], "ABANDON")
        self.assertEqual(self.agir(self.hse, f"{url}clore/").status_code, 400)
        r = self.agir(self.hse, f"{url}clore/", conclusion="Consignes rappelées, sol refait.")
        self.assertEqual((r.data["statut"], r.data["clos_par_nom"], r.data["actions_a_faire"]), ("CLOS", "Hse", 0))
        self.assertEqual(self.agir(self.hse, ACTIONS, **action).status_code, 400)                 # clos
        self.client.force_authenticate(self.hse)
        self.assertEqual(self.client.patch(url, {"lieu": "x"}, format="json").status_code, 403)
        self.assertEqual(self.agir(self.hse, f"{url}rouvrir/").data["statut"], "ANALYSE")
        self.assertEqual(Evenement.objects.get(pk=id).clos_le, None)
