import datetime
from decimal import Decimal

from django.contrib.auth.models import Group
from django.core import mail
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.core import rappels
from apps.core.models import Site, Utilisateur

from .conges import jours_ouvrables, mois_entiers
from .models import Salarie

ABSENCES = "/api/rh/absences/"
J = datetime.date


class CalculTests(APITestCase):
    def test_jours_ouvrables_et_mois(self):
        self.assertEqual(jours_ouvrables(J(2026, 11, 9), J(2026, 11, 14)), 6)      # du lundi au samedi
        self.assertEqual(jours_ouvrables(J(2026, 11, 9), J(2026, 11, 15)), 6)      # le dimanche ne compte pas
        self.assertEqual(jours_ouvrables(J(2026, 11, 15), J(2026, 11, 15)), 0)
        self.assertEqual(jours_ouvrables(J(2026, 11, 14), J(2026, 11, 16)), 2)
        self.assertEqual(jours_ouvrables(J(2026, 11, 2), J(2026, 11, 29)), 24)
        self.assertEqual(jours_ouvrables(J(2026, 11, 10), J(2026, 11, 9)), 0)
        self.assertEqual((mois_entiers(J(2026, 1, 15), J(2026, 3, 14)), mois_entiers(J(2026, 1, 15), J(2026, 3, 15))), (1, 2))


class AbsencesTests(APITestCase):
    def setUp(self):
        def compte(nom, *roles, **champs):
            u = Utilisateur.objects.create_user(nom, password="x", first_name=nom.capitalize(), **champs)
            u.groups.add(*Group.objects.filter(name__in=roles))
            return u

        self.rh = compte("gestionnaire", "RH - Gestionnaire", email="rh@example.com")
        self.chef = compte("chef", "RH - Salarié", email="chef@example.com")
        self.agent = compte("agent", "RH - Salarié", email="agent@example.com")
        self.collegue = compte("collegue", "RH - Salarié")
        self.sans_dossier = compte("nouveau", "RH - Salarié")
        site = Site.objects.get(code="SIEGE")
        self.auj = timezone.localdate()
        il_y_a_10_mois = self.auj - datetime.timedelta(days=310)
        self.s_chef = Salarie.objects.create(nom="Chef", prenoms="C", site=site, utilisateur=self.chef, date_embauche=J(2020, 1, 1))
        self.s_agent = Salarie.objects.create(nom="Agent", prenoms="A", site=site, utilisateur=self.agent, responsable=self.s_chef,
                                              date_embauche=J(2020, 1, 1), conges_depuis=il_y_a_10_mois, conges_solde_depart=Decimal("3"))
        self.s_collegue = Salarie.objects.create(nom="Collegue", prenoms="K", site=site, utilisateur=self.collegue, responsable=self.s_chef)
        self.lundi = self.auj + datetime.timedelta(days=(7 - self.auj.weekday()) % 7 + 7)       # un lundi à venir

    def demander(self, par, jours=6, decalage=0, **champs):
        self.client.force_authenticate(par)
        debut = self.lundi + datetime.timedelta(days=decalage)
        return self.client.post(ABSENCES, {"date_debut": str(debut), "date_fin": str(debut + datetime.timedelta(days=jours - 1)), **champs}, format="json")

    def agir(self, par, id, action, **donnees):
        self.client.force_authenticate(par)
        return self.client.post(f"{ABSENCES}{id}/{action}/", donnees, format="json")

    def test_circuit_et_solde(self):
        self.client.force_authenticate(self.agent)
        solde = self.client.get(f"{ABSENCES}solde/").data
        self.assertEqual((solde["acquis"], solde["solde"]), (Decimal("22.0"), Decimal("25.0")))       # 10 mois × 2,2 + 3 repris
        r = self.demander(self.agent, motif="Vacances")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data["statut"], r.data["jours"], r.data["type"], r.data["salarie"]), ("SOUMISE", "6.0", "CONGE", self.s_agent.id))
        self.assertRegex(r.data["numero"], r"^ABS-\d{4}-0001$")
        id = r.data["id"]
        self.assertIn("chevauche", str(self.demander(self.agent, jours=2, decalage=3).data))
        self.assertEqual(self.demander(self.agent, jours=0).status_code, 400)
        self.assertEqual(self.demander(self.sans_dossier).status_code, 400)                        # compte sans dossier
        self.assertEqual(self.demander(self.agent, salarie=self.s_collegue.id, decalage=20).status_code, 403)
        # chacun voit ses demandes ; le responsable voit son équipe
        for compte, nombre in ((self.agent, 1), (self.chef, 1), (self.collegue, 0), (self.rh, 1)):
            self.client.force_authenticate(compte)
            self.assertEqual(self.client.get(ABSENCES).data["count"], nombre, compte)
        self.assertEqual(self.agir(self.collegue, id, "viser").status_code, 404)
        self.assertEqual(self.agir(self.agent, id, "viser").status_code, 403)                      # pas sa propre demande
        self.assertEqual(self.agir(self.rh, id, "approuver").status_code, 400)                     # le responsable d'abord
        self.client.force_authenticate(self.chef)
        self.assertEqual(self.client.get(ABSENCES, {"vue": "a_traiter"}).data["count"], 1)
        r = self.agir(self.chef, id, "viser")
        self.assertEqual((r.data["statut"], r.data["vise_par_nom"]), ("VISEE", "Chef"))
        self.assertEqual(self.agir(self.chef, id, "approuver").status_code, 403)
        self.client.force_authenticate(self.agent)
        self.assertEqual(self.client.get(f"{ABSENCES}solde/").data["en_attente"], Decimal("6.0"))
        r = self.agir(self.rh, id, "approuver")
        self.assertEqual((r.data["statut"], r.data["approuve_par_nom"]), ("APPROUVEE", "Gestionnaire"))
        self.client.force_authenticate(self.agent)
        solde = self.client.get(f"{ABSENCES}solde/").data
        self.assertEqual((solde["pris"], solde["solde"], solde["en_attente"]), (Decimal("6.0"), Decimal("19.0"), 0))
        # solde insuffisant : refusé à l'approbation
        longue = self.demander(self.agent, jours=28, decalage=14).data
        self.agir(self.chef, longue["id"], "viser")
        self.assertIn("insuffisant", str(self.agir(self.rh, longue["id"], "approuver").data))
        self.assertEqual(self.agir(self.rh, longue["id"], "refuser").status_code, 400)             # motif exigé
        self.assertEqual(self.agir(self.rh, longue["id"], "refuser", commentaire="Solde insuffisant").data["statut"], "REFUSEE")
        # annulation : le demandeur avant l'accord final, les RH après, avec motif
        self.assertEqual(self.agir(self.agent, id, "annuler").status_code, 403)
        self.assertEqual(self.agir(self.rh, id, "annuler").status_code, 400)
        self.assertEqual(self.agir(self.rh, id, "annuler", commentaire="Rappel pour chantier").data["statut"], "ANNULEE")
        self.client.force_authenticate(self.agent)
        self.assertEqual(self.client.get(f"{ABSENCES}solde/").data["solde"], Decimal("25.0"))
        nouvelle = self.demander(self.agent).data
        self.assertEqual(self.agir(self.agent, nouvelle["id"], "annuler").data["statut"], "ANNULEE")
        self.assertIn(self.client.delete(f"{ABSENCES}{id}/").status_code, (403, 405))
        self.assertIn(self.client.patch(f"{ABSENCES}{id}/", {"motif": "x"}, format="json").status_code, (403, 405))

    def test_sans_responsable_saisie_rh_planning_et_rappel(self):
        r = self.demander(self.chef)                                # personne au-dessus : directement aux RH
        self.assertEqual(r.data["statut"], "VISEE")
        r = self.demander(self.rh, salarie=self.s_collegue.id, type="MALADIE", jours=3, motif="Certificat médical")
        self.assertEqual((r.status_code, r.data["statut"], r.data["salarie_nom"]), (201, "SOUMISE", "COLLEGUE K"))
        self.assertEqual(self.agir(self.rh, r.data["id"], "viser").data["statut"], "VISEE")       # les RH peuvent viser à la place
        self.assertEqual(self.agir(self.rh, r.data["id"], "approuver").data["statut"], "APPROUVEE")   # pas de solde pour une maladie
        self.demander(self.agent, jours=2)
        fin = str(self.lundi + datetime.timedelta(days=10))
        for compte, attendu in ((self.rh, ["AGENT A", "CHEF C", "COLLEGUE K"]), (self.chef, ["AGENT A", "CHEF C", "COLLEGUE K"]), (self.agent, ["AGENT A"])):
            self.client.force_authenticate(compte)
            self.assertEqual(sorted(d["salarie_nom"] for d in self.client.get(f"{ABSENCES}planning/", {"debut": str(self.lundi), "fin": fin}).data), attendu)
        self.assertEqual(self.client.get(f"{ABSENCES}solde/", {"salarie": self.s_chef.id}).status_code, 403)
        self.client.force_authenticate(self.chef)
        self.assertEqual(self.client.get(f"{ABSENCES}solde/", {"salarie": self.s_agent.id}).data["salarie_nom"], "AGENT A")
        self.assertEqual(self.client.get(f"{ABSENCES}calcul/", {"debut": "2026-11-09", "fin": "2026-11-15"}).data["jours"], 6)
        rappels.envoyer()
        corps = {m.to[0]: m.body for m in mail.outbox}
        self.assertEqual(sorted(corps), ["chef@example.com", "rh@example.com"])
        self.assertIn("AGENT A", corps["chef@example.com"])
        self.assertIn("CHEF C", corps["rh@example.com"])
        self.assertNotIn("AGENT A", corps["rh@example.com"])       # pas encore visée par son responsable
