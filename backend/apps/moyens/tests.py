from django.contrib.auth.models import Group
from rest_framework.test import APITestCase

from apps.core.models import Service, Site, Utilisateur
from apps.referentiels.models import Tiers

from .models import Bien

BIENS = "/api/moyens/biens/"
URL = "/api/moyens/interventions/"


class MoyensTests(APITestCase):
    def setUp(self):
        def utilisateur(nom, role):
            u = Utilisateur.objects.create_user(nom, password="x", first_name=nom.capitalize())
            u.groups.add(Group.objects.get(name=role))
            return u

        self.demandeur = utilisateur("salarie", "Moyens généraux - Demandeur")
        self.autre = utilisateur("autre", "Moyens généraux - Demandeur")
        self.technicien = utilisateur("technicien", "Moyens généraux - Demandeur")
        self.gestionnaire = utilisateur("gestion", "Moyens généraux - Gestionnaire")
        self.service = Service.objects.get(code="COM")
        self.site = Site.objects.get(code="MARCORY")
        self.prestataire = Tiers.objects.create(code="P1", raison_sociale="Froid Service", est_fournisseur=True)
        self.clim = Bien.objects.create(categorie="EQUIPEMENT", designation="Climatiseur split bureau commercial", site=self.site)

    def demander(self, par=None, **champs):
        self.client.force_authenticate(par or self.demandeur)
        donnees = {"service": self.service.id, "site": self.site.id, "categorie": "CLIMATISATION",
                   "objet": "Climatiseur en panne", "bien": self.clim.id, **champs}
        return self.client.post(URL, donnees, format="json")

    def agir(self, utilisateur, id, action, **donnees):
        self.client.force_authenticate(utilisateur)
        return self.client.post(f"{URL}{id}/{action}/", donnees, format="json")

    def etat_du_bien(self):
        self.clim.refresh_from_db()
        return self.clim.etat

    # ----- biens

    def test_inventaire_reserve_au_gestionnaire(self):
        bien = {"categorie": "VEHICULE", "designation": "Pick-up de liaison", "immatriculation": "1234 AB 01", "site": self.site.id}
        self.client.force_authenticate(self.demandeur)
        self.assertEqual(self.client.post(BIENS, bien, format="json").status_code, 403)
        self.assertEqual(self.client.get(BIENS).data["count"], 1)  # mais chacun peut consulter, pour désigner le bien en panne
        self.client.force_authenticate(self.gestionnaire)
        r = self.client.post(BIENS, bien, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data["numero"].startswith("MG-"))
        self.assertNotEqual(r.data["numero"], self.clim.numero)
        self.assertEqual(self.client.get(f"{BIENS}?search=1234").data["count"], 1)
        self.assertEqual(self.client.delete(f"{BIENS}{r.data['id']}/").status_code, 403)  # pas de suppression

    # ----- interventions

    def test_circuit_complet_avec_prestataire(self):
        r = self.demander(bien_en_panne=True)
        self.assertEqual(r.status_code, 201, r.data)
        id = r.data["id"]
        self.assertTrue(r.data["numero"].startswith("INT-"))
        self.assertEqual(self.etat_du_bien(), "EN_PANNE")
        self.assertEqual(self.agir(self.demandeur, id, "prendre_en_charge", prestataire=self.prestataire.id).status_code, 403)
        self.assertEqual(self.agir(self.gestionnaire, id, "prendre_en_charge").status_code, 400)  # personne de désigné
        r = self.agir(self.gestionnaire, id, "prendre_en_charge", prestataire=self.prestataire.id, date_prevue="2026-11-16")
        self.assertEqual((r.data["statut"], r.data["prestataire_nom"], r.data["date_prevue"]), ("EN_COURS", "Froid Service", "2026-11-16"))
        self.assertEqual(self.etat_du_bien(), "REPARATION")
        self.assertEqual(self.agir(self.gestionnaire, id, "realiser").status_code, 400)  # compte rendu obligatoire
        r = self.agir(self.gestionnaire, id, "realiser", compte_rendu="Recharge de gaz et nettoyage", cout="45000")
        self.assertEqual((r.data["statut"], r.data["cout"]), ("REALISEE", "45000"))
        self.assertEqual(self.agir(self.autre, id, "cloturer").status_code, 404)  # ne voit pas la demande
        r = self.agir(self.demandeur, id, "cloturer")
        self.assertEqual(r.data["statut"], "CLOTUREE")
        self.assertEqual(self.etat_du_bien(), "EN_SERVICE")
        self.assertEqual([e["action"] for e in r.data["evenements"]], ["PRISE", "REALISATION", "CLOTURE"])

    def test_intervenant_interne_realise_et_voit_la_demande(self):
        id = self.demander().data["id"]
        self.client.force_authenticate(self.technicien)
        self.assertEqual(self.client.get(f"{URL}{id}/").status_code, 404)
        self.agir(self.gestionnaire, id, "prendre_en_charge", intervenant=self.technicien.id)
        self.client.force_authenticate(self.technicien)
        self.assertEqual(self.client.get(f"{URL}{id}/").status_code, 200)
        self.assertEqual(self.agir(self.autre, id, "realiser", compte_rendu="x").status_code, 404)
        self.assertEqual(self.agir(self.demandeur, id, "realiser", compte_rendu="x").status_code, 403)
        self.assertEqual(self.agir(self.technicien, id, "realiser", compte_rendu="Fusible remplacé").data["statut"], "REALISEE")

    def test_reouverture_si_le_probleme_persiste(self):
        id = self.demander().data["id"]
        self.agir(self.gestionnaire, id, "prendre_en_charge", prestataire=self.prestataire.id)
        self.agir(self.gestionnaire, id, "realiser", compte_rendu="Fait")
        self.assertEqual(self.agir(self.demandeur, id, "rouvrir").status_code, 400)  # motif obligatoire
        self.assertEqual(self.agir(self.demandeur, id, "rouvrir", commentaire="Fuit toujours").data["statut"], "EN_COURS")

    def test_refus_avec_motif(self):
        id = self.demander().data["id"]
        self.assertEqual(self.agir(self.gestionnaire, id, "refuser").status_code, 400)
        self.assertEqual(self.agir(self.gestionnaire, id, "refuser", commentaire="Relève du bailleur").data["statut"], "REFUSEE")
        self.assertEqual(self.agir(self.gestionnaire, id, "prendre_en_charge", prestataire=self.prestataire.id).status_code, 400)

    def test_modification_par_le_demandeur_tant_que_nouvelle(self):
        id = self.demander().data["id"]
        self.client.force_authenticate(self.autre)
        self.assertEqual(self.client.patch(f"{URL}{id}/", {"objet": "x"}, format="json").status_code, 404)
        self.client.force_authenticate(self.demandeur)
        self.assertEqual(self.client.patch(f"{URL}{id}/", {"objet": "Climatiseur bruyant"}, format="json").status_code, 200)
        # la prise en charge ne se force pas par une modification directe
        r = self.client.patch(f"{URL}{id}/", {"compte_rendu": "fait", "cout": "1"}, format="json")
        self.assertEqual(r.data["compte_rendu"], "")
        self.agir(self.gestionnaire, id, "prendre_en_charge", prestataire=self.prestataire.id)
        self.client.force_authenticate(self.demandeur)
        self.assertEqual(self.client.patch(f"{URL}{id}/", {"objet": "y"}, format="json").status_code, 400)

    def test_visibilite(self):
        self.demander()
        self.client.force_authenticate(self.autre)
        self.assertEqual(self.client.get(URL).data["count"], 0)
        self.client.force_authenticate(self.gestionnaire)
        self.assertEqual(self.client.get(URL).data["count"], 1)
        self.client.force_authenticate(self.demandeur)
        self.assertEqual(self.client.get(f"{BIENS}{self.clim.id}/").data["interventions_ouvertes"], 1)
