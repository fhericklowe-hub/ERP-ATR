from datetime import date, timedelta

from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.core.models import Site, Utilisateur
from apps.referentiels.models import Tiers

from .contrats import Contrat, Echeance, ajouter_mois
from .models import Bien

CONTRATS = "/api/moyens/contrats/"
ECHEANCES = "/api/moyens/echeances/"


class ContratsTests(APITestCase):
    def setUp(self):
        def utilisateur(nom, role):
            u = Utilisateur.objects.create_user(nom, password="x")
            u.groups.add(Group.objects.get(name=role))
            return u

        self.salarie = utilisateur("salarie", "Moyens généraux - Demandeur")
        self.gestionnaire = utilisateur("gestion", "Moyens généraux - Gestionnaire")
        self.site = Site.objects.get(code="MARCORY")
        self.assureur = Tiers.objects.create(code="A1", raison_sociale="Assureur d'essai", est_fournisseur=True)
        self.vehicule = Bien.objects.create(categorie="VEHICULE", designation="Pick-up de service", site=self.site)
        self.jour = timezone.localdate()
        self.client.force_authenticate(self.gestionnaire)

    def contrat(self, **champs):
        donnees = {"type": "ASSURANCE", "objet": "Assurance flotte", "prestataire": self.assureur.id,
                   "date_debut": "2026-01-01", "date_fin": "2026-12-31", "preavis_jours": 60, "montant": "2400000", **champs}
        return self.client.post(CONTRATS, donnees, format="json")

    def echeance(self, dans=10, **champs):
        donnees = {"type": "VISITE", "libelle": "Visite technique du pick-up", "bien": self.vehicule.id,
                   "date_echeance": str(self.jour + timedelta(days=dans)), **champs}
        return self.client.post(ECHEANCES, donnees, format="json")

    def test_ajouter_mois(self):
        self.assertEqual(ajouter_mois(date(2026, 1, 31), 1), date(2026, 2, 28))
        self.assertEqual(ajouter_mois(date(2026, 11, 15), 3), date(2027, 2, 15))
        self.assertEqual(ajouter_mois(date(2024, 2, 29), 12), date(2025, 2, 28))

    def test_reserve_au_gestionnaire(self):
        self.contrat()
        self.client.force_authenticate(self.salarie)
        self.assertEqual(self.client.get(CONTRATS).status_code, 403)
        self.assertEqual(self.client.get(ECHEANCES).status_code, 403)
        self.assertEqual(self.contrat().status_code, 403)

    def test_contrat_numerote_et_fin_suivie(self):
        r = self.contrat()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["numero"], "CTR-2026-0001")
        self.assertEqual(r.data["date_limite_preavis"], "2026-11-01")
        fin = Echeance.objects.get(contrat_id=r.data["id"])
        self.assertEqual((fin.type, fin.date_echeance), ("FIN_CONTRAT", date(2026, 11, 1)))
        # Le contrat est prolongé : l'échéance suit, sans doublon.
        self.client.patch(f"{CONTRATS}{r.data['id']}/", {"date_fin": "2027-12-31"}, format="json")
        fin.refresh_from_db()
        self.assertEqual(fin.date_echeance, date(2027, 11, 1))
        self.assertEqual(Echeance.objects.count(), 1)
        # Résilié : plus rien à surveiller.
        self.client.patch(f"{CONTRATS}{r.data['id']}/", {"statut": "RESILIE"}, format="json")
        fin.refresh_from_db()
        self.assertEqual(fin.statut, "ANNULEE")

    def test_dates_du_contrat(self):
        r = self.contrat(date_fin="2025-12-31")
        self.assertEqual(r.status_code, 400)
        self.assertIn("date_fin", r.data)
        self.assertEqual(self.contrat(date_fin=None).status_code, 201)
        self.assertFalse(Echeance.objects.exists())

    def test_situation_et_filtre(self):
        retard = self.echeance(dans=-3).data
        proche = self.echeance(dans=10).data
        loin = self.echeance(dans=90).data
        self.assertEqual([retard["situation"], proche["situation"], loin["situation"]], ["RETARD", "PROCHE", "A_VENIR"])
        self.assertEqual(proche["jours_restants"], 10)
        ids = lambda s: [e["id"] for e in self.client.get(f"{ECHEANCES}?situation={s}").data["results"]]
        self.assertEqual(ids("RETARD"), [retard["id"]])
        self.assertEqual(ids("PROCHE"), [proche["id"]])
        self.assertEqual(ids("ALERTE"), [retard["id"], proche["id"]])

    def test_faire_cree_la_suivante(self):
        e = self.echeance(dans=5, recurrence_mois=12, montant_prevu="15000").data
        r = self.client.post(f"{ECHEANCES}{e['id']}/faire/", {"montant": "17000"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data["statut"], r.data["montant_reel"], r.data["faite_le"]), ("FAITE", "17000", str(self.jour)))
        suivante = r.data["suivante"]
        self.assertEqual(suivante["date_echeance"], str(ajouter_mois(self.jour + timedelta(days=5), 12)))
        self.assertEqual((suivante["statut"], suivante["montant_prevu"], suivante["bien"]), ("A_FAIRE", "17000", self.vehicule.id))
        # Une échéance faite ne se refait pas et ne se modifie plus.
        self.assertEqual(self.client.post(f"{ECHEANCES}{e['id']}/faire/", {}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(f"{ECHEANCES}{e['id']}/", {"libelle": "x"}, format="json").status_code, 400)

    def test_faire_sans_recurrence_ou_date_choisie(self):
        e = self.echeance().data
        r = self.client.post(f"{ECHEANCES}{e['id']}/faire/", {}, format="json")
        self.assertIsNone(r.data["suivante"])
        e = self.echeance().data
        r = self.client.post(f"{ECHEANCES}{e['id']}/faire/", {"prochaine": "2030-06-30"}, format="json")
        self.assertEqual(r.data["suivante"]["date_echeance"], "2030-06-30")
        e = self.echeance().data
        r = self.client.post(f"{ECHEANCES}{e['id']}/faire/", {"prochaine": "2020-01-01"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Echeance.objects.get(pk=e["id"]).statut, "A_FAIRE")

    def test_annuler_avec_motif(self):
        e = self.echeance().data
        self.assertEqual(self.client.post(f"{ECHEANCES}{e['id']}/annuler/", {}, format="json").status_code, 400)
        r = self.client.post(f"{ECHEANCES}{e['id']}/annuler/", {"commentaire": "Véhicule vendu"}, format="json")
        self.assertEqual(r.data["statut"], "ANNULEE")

    def test_actions_refusees_sans_droit(self):
        e = self.echeance().data
        self.client.force_authenticate(self.salarie)
        self.assertEqual(self.client.post(f"{ECHEANCES}{e['id']}/faire/", {}, format="json").status_code, 403)
        self.assertEqual(Contrat.objects.count(), 0)
