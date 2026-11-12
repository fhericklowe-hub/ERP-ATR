from decimal import Decimal

from django.contrib.auth.models import Group
from rest_framework.test import APITestCase

from apps.core.models import Service, Site, Utilisateur
from apps.referentiels.models import CompteCharge, Projet, Tiers

from .budget import DemandeBudget, LigneBudgetaire
from .models import Acheteur

URL = "/api/achats/demandes-budget/"


class DemandeBudgetTests(APITestCase):
    def setUp(self):
        def utilisateur(nom, role):
            u = Utilisateur.objects.create_user(nom, password="x", first_name=nom.capitalize())
            u.groups.add(Group.objects.get(name=role))
            return u

        self.demandeur = utilisateur("demandeur", "Achats - Demandeur")
        self.chef = utilisateur("chef", "Achats - Demandeur")
        self.acheteur = utilisateur("acheteur", "Achats - Acheteur")
        self.responsable = utilisateur("franck", "Achats - Responsable achats")
        self.controleur = utilisateur("cdg", "Achats - Contrôleur de gestion")
        self.raf = utilisateur("raf", "Achats - Direction financière")
        self.dg = utilisateur("dg", "Achats - Direction générale")
        Acheteur.objects.create(utilisateur=self.acheteur)
        self.service = Service.objects.get(code="MG")
        self.service.responsable = self.chef
        self.service.save()
        self.site = Site.objects.get(code="SIEGE")
        self.compte = CompteCharge.objects.get(numero="605520")
        self.projet = Projet.objects.create(numero=2, nom="SPOT", code_analytique="MANZZZZZZ", activite="Manutention", type="SPOT")
        self.ligne = LigneBudgetaire.objects.create(exercice=2026, service=self.service, intitule="Fournitures de bureau",
                                                    compte=self.compte, montant=2000000)
        self.fournisseurs = [Tiers.objects.create(code=f"F{i}", raison_sociale=f"Fournisseur {i}", est_fournisseur=True)
                             for i in range(3)]

    # ----- aides

    def creer(self, par=None, **champs):
        self.client.force_authenticate(par or self.demandeur)
        donnees = {"type": "FG", "service": self.service.id, "site": self.site.id, "projet": self.projet.id,
                   "intitule": "Fournitures de bureau du trimestre", "ligne_budgetaire": self.ligne.id, **champs}
        r = self.client.post(URL, donnees, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        return r.data

    def agir(self, utilisateur, id, action, **donnees):
        self.client.force_authenticate(utilisateur)
        return self.client.post(f"{URL}{id}/{action}/", donnees, format="json")

    def modifier(self, utilisateur, id, **donnees):
        self.client.force_authenticate(utilisateur)
        return self.client.patch(f"{URL}{id}/", donnees, format="json")

    def devis(self, *montants, retenu=0):
        return [{"fournisseur": self.fournisseurs[i].id, "numero": f"D{i}", "montant": str(m), "retenu": i == retenu}
                for i, m in enumerate(montants)]

    def jusqu_a(self, statut, **champs):
        """Fait avancer une nouvelle demande jusqu'au statut voulu, par le chemin normal."""
        montants = champs.pop("montants", (400000, 450000, 500000))
        d = self.creer(**champs)
        id = d["id"]
        etapes = [
            lambda: self.agir(self.demandeur, id, "soumettre"),
            lambda: self.agir(self.chef, id, "valider"),
            lambda: self.agir(self.dg, id, "valider"),  # accord de principe, seulement s'il est demandé
            lambda: (self.modifier(self.acheteur, id, devis=self.devis(*montants), critere_prix=True),
                     self.agir(self.acheteur, id, "proposer"))[1],
            lambda: self.agir(self.responsable, id, "valider"),
            lambda: (self.modifier(self.controleur, id, service_impute=self.service.id, compte=self.compte.id),
                     self.agir(self.controleur, id, "valider"))[1],
            lambda: self.agir(self.raf, id, "valider"),
            lambda: self.agir(self.dg, id, "valider"),
        ]
        for etape in etapes:
            actuel = DemandeBudget.objects.get(pk=id).statut
            if actuel == statut:
                break
            if etape is etapes[2] and actuel != "ATT_ACCORD":
                continue
            r = etape()
            self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(DemandeBudget.objects.get(pk=id).statut, statut)
        return id

    def lire(self, id, par=None):
        self.client.force_authenticate(par or self.responsable)
        return self.client.get(f"{URL}{id}/").data

    # ----- circuit

    def test_numerotation_par_type(self):
        d = self.creer(prevu_budget=False, ligne_budgetaire=None)
        self.assertTrue(d["numero"].startswith("DAB-2026-"))
        self.assertEqual((d["compte_nom"], d["ligne_budgetaire_nom"], d["projet_nom"], d["acheteur_nom"]), ("", "", "SPOT", ""))
        self.assertTrue(self.creer(type="DI_NP", nature="INFORMATIQUE")["numero"].startswith("DI-2026-"))

    def test_frais_generaux_sous_le_seuil_sans_direction_generale(self):
        id = self.jusqu_a("VALIDEE")
        d = self.lire(id)
        self.assertEqual(Decimal(d["montant"]), 400000)
        self.assertEqual(d["motifs_dg"], [])
        self.assertEqual([s["etape"] for s in d["signatures"]],
                         ["Responsable du service", "Responsable achats", "Contrôle de gestion", "Direction financière"])
        self.assertTrue(all(s["auteur"] for s in d["signatures"]))
        self.assertEqual(d["acheteur"], self.acheteur.id)  # attribuée à l'entrée en consultation

    def test_au_dessus_du_seuil_la_direction_generale_valide(self):
        id = self.jusqu_a("ATT_DG", montants=(1200000, 1300000, 1400000))
        self.assertIn("montant supérieur à 1 000 000 francs CFA", self.lire(id)["motifs_dg"])
        self.assertEqual(self.agir(self.raf, id, "valider").status_code, 403)
        self.assertEqual(self.agir(self.dg, id, "valider").data["statut"], "VALIDEE")

    def test_situation_budgetaire(self):
        self.jusqu_a("VALIDEE", montants=(900000, 950000, 990000))
        id = self.jusqu_a("ATT_RAF", montants=(950000, 990000, 999000))
        s = self.lire(id)["situation_budget"]
        self.assertEqual([s[c] for c in ["budget", "engage", "disponible", "a_engager", "solde"]],
                         [2000000, 900000, 1100000, 950000, 150000])
        self.assertEqual(self.agir(self.raf, id, "valider").data["statut"], "VALIDEE")  # sous le seuil, dans le budget
        autre = self.jusqu_a("ATT_DG", montants=(400000, 450000, 500000))  # 1 850 000 engagés : 400 000 dépasse
        self.assertEqual(self.lire(autre)["motifs_dg"], ["dépassement de la ligne budgétaire"])

    def test_hors_budget_accord_de_la_direction_generale_avant_consultation(self):
        self.client.force_authenticate(self.demandeur)
        d = self.creer(prevu_budget=False, ligne_budgetaire=None)
        self.assertEqual(self.agir(self.demandeur, d["id"], "soumettre").status_code, 400)  # motif obligatoire
        self.modifier(self.demandeur, d["id"], motif_hors_budget="Panne imprévue du groupe électrogène")
        self.agir(self.demandeur, d["id"], "soumettre")
        self.assertEqual(self.agir(self.chef, d["id"], "valider").data["statut"], "ATT_ACCORD")
        self.assertEqual(self.agir(self.responsable, d["id"], "valider").status_code, 403)
        self.assertEqual(self.agir(self.dg, d["id"], "valider").data["statut"], "CONSULT")

    def test_investissement_direction_generale_au_debut_et_a_la_fin(self):
        id = self.jusqu_a("ATT_DG", type="DI_NP", nature="INFORMATIQUE", montants=(300000,))
        d = self.lire(id)
        self.assertIn("demande d'investissement", d["motifs_dg"])
        self.assertEqual([e["action"] for e in d["evenements"]][:3], ["SOUMISSION", "VALIDATION", "ACCORD"])
        self.assertEqual(d["signatures"][-1]["etape"], "Direction générale")

    def test_investissement_controles_de_saisie(self):
        d = self.creer(type="DI_P", nature="INFORMATIQUE")
        r = self.agir(self.demandeur, d["id"], "soumettre")
        self.assertEqual(r.status_code, 400)
        self.assertIn("développement ou d'un renouvellement", str(r.data))
        self.assertIn("ne correspond pas", str(r.data))

    def test_trois_devis_ou_justification(self):
        id = self.jusqu_a("CONSULT")
        self.modifier(self.acheteur, id, devis=self.devis(400000))
        self.assertEqual(self.agir(self.acheteur, id, "proposer").status_code, 400)
        self.modifier(self.acheteur, id, justification_devis="Fournisseur exclusif")
        self.assertEqual(self.agir(self.acheteur, id, "proposer").data["statut"], "ATT_ACHATS")

    def test_un_devis_retenu_et_un_seul(self):
        id = self.jusqu_a("CONSULT")
        tous = [{**d, "retenu": True} for d in self.devis(1, 2, 3)]
        self.assertEqual(self.modifier(self.acheteur, id, devis=tous).status_code, 400)
        aucun = [{**d, "retenu": False} for d in self.devis(1, 2, 3)]
        self.modifier(self.acheteur, id, devis=aucun)
        self.assertEqual(self.agir(self.acheteur, id, "proposer").status_code, 400)

    def test_chacun_ne_modifie_que_sa_partie(self):
        id = self.jusqu_a("CONSULT")
        self.assertEqual(self.modifier(self.demandeur, id, intitule="Autre").status_code, 403)
        self.assertEqual(self.modifier(self.acheteur, id, intitule="Autre").status_code, 400)
        self.assertEqual(self.modifier(self.controleur, id, compte=self.compte.id).status_code, 403)
        id = self.jusqu_a("ATT_CDG")
        self.assertEqual(self.modifier(self.acheteur, id, devis=self.devis(1, 2, 3)).status_code, 403)
        self.assertEqual(self.agir(self.controleur, id, "valider").status_code, 400)  # imputation manquante
        self.assertEqual(self.modifier(self.controleur, id, compte=self.compte.id, service_impute=self.service.id).status_code, 200)

    def test_refus_et_renvoi(self):
        id = self.jusqu_a("ATT_RAF")
        self.assertEqual(self.agir(self.raf, id, "renvoyer").status_code, 400)  # motif obligatoire
        self.assertEqual(self.agir(self.raf, id, "renvoyer", commentaire="Préciser le besoin").data["statut"], "BROUILLON")
        d = self.lire(id)
        self.assertFalse(any(s["auteur"] for s in d["signatures"]))  # les visas précédents ne valent plus
        self.agir(self.demandeur, id, "soumettre")
        self.assertEqual(self.agir(self.chef, id, "refuser", commentaire="Non prioritaire").data["statut"], "REFUSEE")
        self.assertEqual(self.agir(self.demandeur, id, "soumettre").status_code, 400)

    def test_visibilite(self):
        id = self.jusqu_a("ATT_SERVICE")
        autre = Utilisateur.objects.create_user("autre", password="x")
        autre.groups.add(Group.objects.get(name="Achats - Demandeur"))
        self.client.force_authenticate(autre)
        self.assertEqual(self.client.get(f"{URL}{id}/").status_code, 404)
        self.assertEqual(self.client.get(URL).data["count"], 0)
        for u in (self.demandeur, self.chef, self.acheteur, self.dg):
            self.client.force_authenticate(u)
            self.assertEqual(self.client.get(f"{URL}{id}/").status_code, 200)

    def test_bon_de_commande_depuis_une_demande_validee(self):
        en_cours = self.jusqu_a("ATT_RAF")
        id = self.jusqu_a("VALIDEE")
        self.client.force_authenticate(self.acheteur)
        bon = {"fournisseur": self.fournisseurs[0].id, "site": self.site.id, "service": self.service.id,
               "lignes": [{"designation": "Fournitures de bureau", "quantite": "1", "prix_unitaire": "400000"}]}
        self.assertEqual(self.client.post("/api/achats/bons-commande/", {**bon, "demande_budget": en_cours}, format="json").status_code, 400)
        self.assertEqual(self.client.post("/api/achats/bons-commande/", bon, format="json").status_code, 400)  # sans demande
        r = self.client.post("/api/achats/bons-commande/", {**bon, "demande_budget": id}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data["demande_numero"].startswith("DAB-"))
        self.assertTrue(self.client.get(f"/api/achats/bons-commande/{r.data['id']}/pdf/").content.startswith(b"%PDF"))
        self.assertEqual(self.lire(id)["bons_commande"][0]["numero"], r.data["numero"])

    def test_pdf(self):
        id = self.jusqu_a("VALIDEE")
        self.client.force_authenticate(self.demandeur)
        self.assertTrue(self.client.get(f"{URL}{id}/pdf/").content.startswith(b"%PDF"))
        brouillon = self.creer(type="DI_P", nature="LEVAGE", motif_investissement="DEVELOPPEMENT")
        self.assertTrue(self.client.get(f"{URL}{brouillon['id']}/pdf/").content.startswith(b"%PDF"))

    def test_lignes_budgetaires_reservees_au_controle_de_gestion(self):
        ligne = {"exercice": 2026, "service": self.service.id, "intitule": "Carburant", "montant": "5000000"}
        self.client.force_authenticate(self.demandeur)
        self.assertEqual(self.client.post("/api/achats/lignes-budgetaires/", ligne, format="json").status_code, 403)
        self.assertEqual(self.client.get("/api/achats/lignes-budgetaires/").status_code, 200)
        self.client.force_authenticate(self.controleur)
        r = self.client.post("/api/achats/lignes-budgetaires/", ligne, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Decimal(r.data["disponible"]), 5000000)
