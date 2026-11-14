from django.contrib.auth.models import Group
from rest_framework.test import APITestCase

from apps.core.models import Site, Utilisateur
from apps.referentiels.models import Tiers

URL = "/api/commercial/opportunites/"
DEVIS = "/api/commercial/devis/"


class OpportuniteTests(APITestCase):
    def setUp(self):
        def utilisateur(nom, *roles):
            u = Utilisateur.objects.create_user(nom, password="x", first_name=nom.capitalize())
            u.groups.add(*Group.objects.filter(name__in=roles))
            return u

        self.commercial = utilisateur("vendeur", "Commercial - Commercial")
        self.collegue = utilisateur("collegue", "Commercial - Commercial")
        self.responsable = utilisateur("responsable", "Commercial - Responsable")
        self.finance = utilisateur("finance", "Commercial - Validation finance")
        self.dg = utilisateur("dg", "Commercial - Validation DG")
        self.etranger = utilisateur("etranger", "Technique - Mécanicien")
        self.site = Site.objects.get(code="SIEGE")
        self.client_a = Tiers.objects.create(code="50100", raison_sociale="Client Essai", est_client=True)
        self.autre_client = Tiers.objects.create(code="50101", raison_sociale="Autre Client", est_client=True)

    def corps(self, **champs):
        return {"nom_affaire": "Levage de transformateurs", "client": self.client_a.id, "site": self.site.id, "activite": "LEVAGE",
                "type_affaire": "PRESTATION", "origine": "APPEL_OFFRES", "ca_previsionnel": "12000000", "marge_previsionnelle": "3000000",
                "probabilite": 60, **champs}

    def creer(self, par=None, **champs):
        self.client.force_authenticate(par or self.commercial)
        return self.client.post(URL, self.corps(**champs), format="json")

    def agir(self, utilisateur, id, action, **donnees):
        self.client.force_authenticate(utilisateur)
        return self.client.post(f"{URL}{id}/{action}/", donnees, format="json")

    def go(self):
        id = self.creer().data["id"]
        self.agir(self.commercial, id, "soumettre")
        for qui in (self.responsable, self.finance, self.dg):
            self.agir(qui, id, "valider")
        return id

    def test_circuit_complet_jusqu_au_go(self):
        r = self.creer()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data["numero"].startswith("GNG-"))
        self.assertEqual((r.data["statut"], str(r.data["taux_marge"]), r.data["commercial_nom"]), ("BROUILLON", "25.0", "Vendeur"))
        id = r.data["id"]
        self.assertEqual(self.agir(self.collegue, id, "soumettre").status_code, 403)       # fiche d'un autre commercial
        self.assertEqual(self.agir(self.commercial, id, "soumettre").data["statut"], "ATT_RESP")
        # chacun son tour, dans l'ordre : responsable commercial, finance, DG
        self.assertEqual(self.agir(self.finance, id, "valider").status_code, 403)
        self.assertEqual(self.agir(self.dg, id, "valider").status_code, 403)
        self.assertEqual(self.agir(self.commercial, id, "valider").status_code, 403)
        self.assertEqual(self.agir(self.responsable, id, "valider", commentaire="Client connu").data["statut"], "ATT_FIN")
        self.assertEqual(self.agir(self.responsable, id, "valider").status_code, 403)
        self.assertEqual(self.agir(self.finance, id, "valider").data["statut"], "ATT_DG")
        r = self.agir(self.dg, id, "valider", commentaire="Go")
        self.assertEqual(r.data["statut"], "GO")
        self.assertEqual([(d["action"], d["niveau"]) for d in r.data["decisions"]],
                         [("SOUMIS", ""), ("VALIDE", "ATT_RESP"), ("VALIDE", "ATT_FIN"), ("VALIDE", "ATT_DG")])
        self.assertEqual(self.agir(self.dg, id, "valider").status_code, 400)               # plus rien à valider

    def test_no_go_renvoi_et_annulation_demandent_un_motif(self):
        id = self.creer().data["id"]
        self.agir(self.commercial, id, "soumettre")
        self.assertEqual(self.agir(self.responsable, id, "refuser").status_code, 400)
        r = self.agir(self.responsable, id, "renvoyer", commentaire="Précisez le lieu")
        self.assertEqual((r.status_code, r.data["statut"], r.data["modifiable"]), (200, "BROUILLON", True))
        self.client.force_authenticate(self.commercial)
        self.assertEqual(self.client.patch(f"{URL}{id}/", {"lieu": "Port d'Abidjan"}, format="json").status_code, 200)
        self.agir(self.commercial, id, "soumettre")
        self.agir(self.responsable, id, "valider")
        r = self.agir(self.finance, id, "refuser", commentaire="Marge insuffisante")
        self.assertEqual((r.data["statut"], r.data["decisions"][-1]["niveau_libelle"]), ("NO_GO", "Finance"))
        self.assertEqual(self.agir(self.commercial, id, "annuler", commentaire="x").status_code, 400)   # déjà close
        autre = self.creer().data["id"]
        self.assertEqual(self.agir(self.commercial, autre, "annuler").status_code, 400)
        self.assertEqual(self.agir(self.commercial, autre, "annuler", commentaire="Affaire perdue").data["statut"], "ANNULEE")

    def test_modification_seulement_en_brouillon_et_par_le_commercial(self):
        id = self.creer().data["id"]
        self.client.force_authenticate(self.collegue)
        self.assertEqual(self.client.patch(f"{URL}{id}/", {"lieu": "x"}, format="json").status_code, 403)
        self.assertEqual(self.creer(marge_previsionnelle="99999999").status_code, 400)       # marge supérieure au CA
        self.assertEqual(self.creer(date_lancement_ao="2026-12-01", date_limite_ao="2026-11-01").status_code, 400)
        self.agir(self.commercial, id, "soumettre")
        self.client.force_authenticate(self.commercial)
        self.assertEqual(self.client.patch(f"{URL}{id}/", {"lieu": "x"}, format="json").status_code, 400)
        self.assertEqual(self.creer(par=self.etranger).status_code, 403)
        self.assertEqual(self.client.get(f"{URL}exporter/").status_code, 403)
        self.client.force_authenticate(self.commercial)
        self.assertEqual(self.client.get(f"{URL}exporter/").status_code, 200)

    def test_pas_de_devis_sans_go(self):
        corps = {"client": self.client_a.id, "libelle": "Levage", "site": self.site.id,
                 "lignes": [{"designation": "Grue 50 t", "quantite": "1", "prix_unitaire": "500000", "duree": "1"}]}
        self.client.force_authenticate(self.commercial)
        self.assertEqual(self.client.post(DEVIS, corps, format="json").status_code, 400)                        # pas de fiche
        id = self.creer().data["id"]
        r = self.client.post(DEVIS, {**corps, "opportunite": id}, format="json")
        self.assertEqual(r.status_code, 400)                                                                   # fiche en brouillon
        self.assertIn("n'a pas reçu le GO", str(r.data))
        go = self.go()
        self.client.force_authenticate(self.commercial)
        r = self.client.post(DEVIS, {**corps, "opportunite": go, "client": self.autre_client.id}, format="json")
        self.assertEqual(r.status_code, 400)                                                                   # autre client
        r = self.client.post(DEVIS, {**corps, "opportunite": go}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data["opportunite_numero"].startswith("GNG-"))
        fiche = self.client.get(f"{URL}{go}/").data
        self.assertEqual([d["numero"] for d in fiche["devis"]], [r.data["numero"]])
        self.assertEqual(self.agir(self.commercial, go, "annuler", commentaire="Abandon").status_code, 400)    # un devis est établi dessus
        self.assertEqual(self.client.patch(f"{DEVIS}{r.data['id']}/", {"opportunite": id}, format="json").status_code, 400)
