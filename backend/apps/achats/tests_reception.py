from decimal import Decimal

from django.contrib.auth.models import Group

from apps.core.models import Utilisateur

from .tests_commande import SocleCommande


class BonReceptionTests(SocleCommande):
    """Réception d'un bon de commande transmis : 3 oxygène, 2 acétylène, 5 locations, 5 livraisons."""

    def setUp(self):
        super().setUp()
        self.magasinier = Utilisateur.objects.create_user("magasin", password="x", first_name="Magasin")
        self.magasinier.groups.add(Group.objects.get(name="Achats - Magasinier"))
        self.bon = self.creer().data
        self.lignes = [l["id"] for l in self.bon["lignes"]]

    def transmettre(self):
        id = self.bon["id"]
        self.agir(self.acheteur, id, "soumettre")
        self.agir(self.responsable, id, "valider")
        self.agir(self.controleur, id, "valider")
        self.assertEqual(self.agir(self.acheteur, id, "transmettre").data["statut"], "TRANSMIS")

    def recevoir(self, quantites, par=None, valider=True, **champs):
        """quantites : {indice de ligne de commande: quantité reçue}"""
        self.client.force_authenticate(par or self.magasinier)
        lignes = [{"ligne_commande": self.lignes[i], "quantite_recue": str(q), "quantite_stock": str(q)}
                  for i, q in quantites.items()]
        r = self.client.post("/api/achats/bons-reception/",
                             {"commande": self.bon["id"], "numero_livraison": "BL-1", "lignes": lignes, **champs},
                             format="json")
        if valider and r.status_code == 201:
            return self.action(par or self.magasinier, r.data["id"], "valider")
        return r

    def action(self, utilisateur, id, action, **donnees):
        self.client.force_authenticate(utilisateur)
        return self.client.post(f"/api/achats/bons-reception/{id}/{action}/", donnees, format="json")

    def commande(self):
        self.client.force_authenticate(self.acheteur)
        return self.client.get(f"/api/achats/bons-commande/{self.bon['id']}/").data

    def test_pas_de_reception_avant_transmission(self):
        self.assertEqual(self.recevoir({0: 1}).status_code, 400)
        self.assertEqual(self.commande()["etat_reception"], "")

    def test_reception_partielle_puis_complete(self):
        self.transmettre()
        self.assertEqual(self.commande()["etat_reception"], "AUCUNE")
        r = self.recevoir({0: 2, 1: 2})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["statut"], "VALIDE")
        self.assertTrue(r.data["numero"].startswith("BR-"))
        self.assertEqual(Decimal(r.data["total_ht"]), Decimal(2 * 39627 + 2 * 112489))
        c = self.commande()
        self.assertEqual(c["etat_reception"], "PARTIELLE")
        self.assertEqual([Decimal(l["quantite_recue"]) for l in c["lignes"]], [2, 2, 0, 0])
        self.assertEqual(self.recevoir({0: 1, 2: 5, 3: 5}).status_code, 200)
        c = self.commande()
        self.assertEqual(c["etat_reception"], "COMPLETE")
        self.assertEqual(len(c["receptions"]), 2)
        self.assertEqual([e["action"] for e in c["evenements"]][-2:], ["RECEPTION", "RECEPTION"])

    def test_on_ne_recoit_pas_plus_que_le_reste_a_recevoir(self):
        self.transmettre()
        self.recevoir({0: 2})
        r = self.recevoir({0: 2})
        self.assertEqual(r.status_code, 400)
        self.assertIn("1 restant", str(r.data))

    def test_un_brouillon_ne_compte_pas(self):
        self.transmettre()
        r = self.recevoir({0: 3}, valider=False)
        self.assertEqual(r.data["statut"], "BROUILLON")
        self.assertEqual(self.commande()["etat_reception"], "AUCUNE")
        # le brouillon se corrige, puis se valide
        self.client.force_authenticate(self.magasinier)
        lignes = [{"ligne_commande": self.lignes[0], "quantite_recue": "1", "quantite_stock": "0"}]
        r2 = self.client.patch(f"/api/achats/bons-reception/{r.data['id']}/", {"lignes": lignes}, format="json")
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertEqual(self.action(self.magasinier, r.data["id"], "valider").status_code, 200)
        self.assertEqual(Decimal(self.commande()["lignes"][0]["quantite_recue"]), 1)

    def test_reception_validee_non_modifiable(self):
        self.transmettre()
        r = self.recevoir({0: 1})
        self.client.force_authenticate(self.magasinier)
        r2 = self.client.patch(f"/api/achats/bons-reception/{r.data['id']}/", {"numero_livraison": "X"}, format="json")
        self.assertEqual(r2.status_code, 400)
        self.assertEqual(self.action(self.magasinier, r.data["id"], "valider").status_code, 400)

    def test_controles_de_saisie(self):
        self.transmettre()
        self.assertEqual(self.recevoir({}).status_code, 400)  # rien de reçu : validation refusée
        self.assertEqual(self.recevoir({0: 0}).status_code, 400)
        self.client.force_authenticate(self.magasinier)
        trop = [{"ligne_commande": self.lignes[0], "quantite_recue": "1", "quantite_stock": "2"}]
        r = self.client.post("/api/achats/bons-reception/", {"commande": self.bon["id"], "lignes": trop}, format="json")
        self.assertEqual(r.status_code, 400)
        autre = self.creer().data  # une ligne d'un autre bon de commande
        ligne = [{"ligne_commande": autre["lignes"][0]["id"], "quantite_recue": "1"}]
        r = self.client.post("/api/achats/bons-reception/", {"commande": self.bon["id"], "lignes": ligne}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_materiel_avec_serie_et_immatriculation(self):
        self.transmettre()
        self.client.force_authenticate(self.magasinier)
        ligne = [{"ligne_commande": self.lignes[0], "quantite_recue": "1", "numero_materiel": "503311", "numero_serie": "LA996RDC2T0LXP005",
                  "immatriculation": "AB-173-KR-01"}]
        r = self.client.post("/api/achats/bons-reception/", {"commande": self.bon["id"], "lignes": ligne}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["lignes"][0]["immatriculation"], "AB-173-KR-01")
        r = self.client.get("/api/achats/bons-reception/?search=AB-173")
        self.assertEqual(r.data["count"], 1)

    def test_droits(self):
        self.transmettre()
        self.assertEqual(self.recevoir({0: 1}, par=self.demandeur).status_code, 403)
        self.assertEqual(self.recevoir({0: 1}, par=self.controleur).status_code, 403)
        r = self.recevoir({0: 1}, valider=False)
        self.assertEqual(self.action(self.acheteur, r.data["id"], "valider").status_code, 403)  # pas son bon
        self.client.force_authenticate(self.controleur)
        self.assertEqual(self.client.get(f"/api/achats/bons-reception/{r.data['id']}/").status_code, 200)

    def test_annulation(self):
        self.transmettre()
        r = self.recevoir({0: 3})
        id = r.data["id"]
        self.assertEqual(self.action(self.magasinier, id, "annuler", commentaire="Erreur").status_code, 403)
        self.assertEqual(self.action(self.responsable, id, "annuler").status_code, 400)  # motif obligatoire
        # un bon de commande reçu ne s'annule pas tant que la réception tient
        self.assertEqual(self.agir(self.responsable, self.bon["id"], "annuler", commentaire="x").status_code, 400)
        r = self.action(self.responsable, id, "annuler", commentaire="Erreur de bon de commande")
        self.assertEqual(r.data["statut"], "ANNULE")
        c = self.commande()
        self.assertEqual(c["etat_reception"], "AUCUNE")
        self.assertEqual(c["evenements"][-1]["action"], "RECEP_ANNUL")
        self.assertEqual(self.recevoir({0: 3}).status_code, 200)  # la quantité redevient à recevoir

    def test_cloture_d_une_commande_recue_en_partie(self):
        self.transmettre()
        id = self.bon["id"]
        self.recevoir({0: 3, 1: 2})
        self.assertEqual(self.agir(self.magasinier, id, "cloturer", commentaire="x").status_code, 403)
        self.assertEqual(self.agir(self.acheteur, id, "cloturer").status_code, 400)  # incomplète : motif obligatoire
        r = self.agir(self.acheteur, id, "cloturer", commentaire="Location arrêtée")
        self.assertEqual((r.data["statut"], r.data["etat_reception"]), ("CLOTURE", "PARTIELLE"))
        self.assertEqual(self.recevoir({2: 5}).status_code, 400)  # plus de réception sur une commande clôturée
        self.assertEqual(self.agir(self.acheteur, id, "decloturer").data["statut"], "TRANSMIS")
        self.recevoir({2: 5, 3: 5})
        self.assertEqual(self.agir(self.acheteur, id, "cloturer").data["statut"], "CLOTURE")  # complète : sans motif

    def test_le_receptionnaire_abandonne_son_brouillon(self):
        self.transmettre()
        r = self.recevoir({0: 1}, valider=False)
        self.assertEqual(self.action(self.magasinier, r.data["id"], "annuler", commentaire="Doublon").data["statut"], "ANNULE")

    def test_pdf(self):
        self.transmettre()
        r = self.recevoir({0: 3, 1: 2})
        self.client.force_authenticate(self.magasinier)
        pdf = self.client.get(f"/api/achats/bons-reception/{r.data['id']}/pdf/")
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        self.assertTrue(self.client.get(f"/api/achats/bons-commande/{self.bon['id']}/pdf/").content.startswith(b"%PDF"))
