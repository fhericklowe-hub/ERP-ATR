from decimal import Decimal

from django.contrib.auth.models import Group

from apps.core.models import Utilisateur

from .tests_commande import SocleCommande
from .tests_reception import BonReceptionTests

URL = "/api/achats/factures/"
RECU_01 = 2 * 39627 + 2 * 112489   # 2 premières lignes reçues, 2 fois


class FactureTests(SocleCommande):
    # On réutilise la mise en place d'une commande transmise et reçue, sans rejouer les tests de réception.
    transmettre, recevoir, action = BonReceptionTests.transmettre, BonReceptionTests.recevoir, BonReceptionTests.action

    def setUp(self):
        super().setUp()
        self.magasinier = Utilisateur.objects.create_user("magasin", password="x", first_name="Magasin")
        self.magasinier.groups.add(Group.objects.get(name="Achats - Magasinier"))
        self.bon = self.creer().data
        self.lignes = [l["id"] for l in self.bon["lignes"]]
        self.simple = Utilisateur.objects.create_user("simple", password="x")
        self.transmettre()
        self.recevoir({0: 2, 1: 2})

    def facturer(self, par=None, ht=RECU_01, **champs):
        self.client.force_authenticate(par or self.acheteur)
        return self.client.post(URL, {"commande": self.bon["id"], "numero_facture": "F-2026-77", "montant_ht": str(ht),
                                      "montant_ttc": str(Decimal(ht) * Decimal("1.18")), **champs}, format="json")

    def agir_facture(self, utilisateur, id, nom, **donnees):
        self.client.force_authenticate(utilisateur)
        return self.client.post(f"{URL}{id}/{nom}/", donnees, format="json")

    def test_facture_conforme_bon_a_payer_puis_paiement(self):
        r = self.facturer()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data["numero"].startswith("FF-"))
        self.assertEqual((r.data["statut"], r.data["rapprochement"]["conforme"], r.data["peut_bon_a_payer"]), ("A_VERIFIER", True, False))
        id = r.data["id"]
        self.assertEqual(self.agir_facture(self.acheteur, id, "bon_a_payer").status_code, 403)
        r = self.agir_facture(self.responsable, id, "bon_a_payer")
        self.assertEqual((r.status_code, r.data["statut"]), (200, "BON_A_PAYER"))
        self.assertEqual(self.agir_facture(self.acheteur, id, "payer").status_code, 403)
        r = self.agir_facture(self.responsable, id, "payer", date="2026-11-20", reference="VIR-123")
        self.assertEqual((r.data["statut"], r.data["payee_le"], r.data["reference_paiement"]), ("PAYEE", "2026-11-20", "VIR-123"))
        self.assertEqual(self.agir_facture(self.responsable, id, "annuler", commentaire="x").status_code, 400)

    def test_ecart_exige_une_justification(self):
        r = self.facturer(ht=RECU_01 + 50000)
        self.assertEqual((r.data["rapprochement"]["conforme"], r.data["rapprochement"]["sens"]), (False, "facture_superieure"))
        self.assertEqual(Decimal(r.data["rapprochement"]["ecart_ht"]), 50000)
        id = r.data["id"]
        self.assertEqual(self.agir_facture(self.responsable, id, "bon_a_payer").status_code, 400)
        r = self.agir_facture(self.responsable, id, "bon_a_payer", commentaire="Transport accepté par téléphone")
        self.assertEqual((r.status_code, r.data["commentaire_ecart"]), (200, "Transport accepté par téléphone"))

    def test_le_cumul_des_factures_compte(self):
        self.facturer(ht=100000, numero_facture="A")
        r = self.facturer(ht=RECU_01 - 100000, numero_facture="B")
        self.assertTrue(r.data["rapprochement"]["conforme"])
        r = self.facturer(ht=1000, numero_facture="C")
        self.assertEqual(Decimal(r.data["rapprochement"]["ecart_ht"]), 1000)

    def test_doublon_et_refus(self):
        self.assertEqual(self.facturer().status_code, 201)
        self.assertEqual(self.facturer(numero_facture="f-2026-77").status_code, 400)         # même facture du même fournisseur
        self.assertEqual(self.facturer(ht=0).status_code, 400)
        self.assertEqual(self.facturer(montant_ttc="10").status_code, 400)                    # TTC inférieur au HT
        self.assertEqual(self.facturer(par=self.simple, numero_facture="Z").status_code, 403)
        self.assertEqual(self.facturer(par=self.magasinier, numero_facture="Z").status_code, 403)

    def test_commande_non_transmise_refusee_et_annulation_libere_le_numero(self):
        autre = self.creer().data["id"]
        self.client.force_authenticate(self.acheteur)
        r = self.client.post(URL, {"commande": autre, "numero_facture": "Q", "montant_ht": "100", "montant_ttc": "118"}, format="json")
        self.assertEqual(r.status_code, 400)
        id = self.facturer().data["id"]
        self.assertEqual(self.agir_facture(self.acheteur, id, "annuler").status_code, 400)    # motif obligatoire
        self.assertEqual(self.agir_facture(self.acheteur, id, "annuler", commentaire="Saisie erronée").data["statut"], "ANNULEE")
        self.assertEqual(self.facturer().status_code, 201)

    def test_modification_seulement_a_verifier_et_export(self):
        id = self.facturer().data["id"]
        self.client.force_authenticate(self.acheteur)
        self.assertEqual(self.client.patch(f"{URL}{id}/", {"observations": "ok"}, format="json").status_code, 200)
        self.agir_facture(self.responsable, id, "bon_a_payer")
        self.client.force_authenticate(self.responsable)
        self.assertEqual(self.client.patch(f"{URL}{id}/", {"observations": "tard"}, format="json").status_code, 400)
        self.assertIn(self.client.delete(f"{URL}{id}/").status_code, (403, 405))
        r = self.client.get(f"{URL}exporter/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheetml", r["Content-Type"])
