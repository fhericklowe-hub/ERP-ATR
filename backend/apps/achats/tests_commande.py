from decimal import Decimal

from django.contrib.auth.models import Group
from django.test import SimpleTestCase
from rest_framework.test import APITestCase

from apps.core.lettres import montant_en_lettres
from apps.core.models import Service, Site, Utilisateur
from apps.referentiels.models import Tiers, Unite

from .models import Acheteur, DemandeAchat


class LettresTests(SimpleTestCase):
    def test_montants(self):
        cas = {
            0: "ZÉRO FRANCS CFA",
            71: "SOIXANTE ET ONZE FRANCS CFA",
            80: "QUATRE-VINGTS FRANCS CFA",
            91: "QUATRE-VINGT-ONZE FRANCS CFA",
            200: "DEUX CENTS FRANCS CFA",
            201: "DEUX CENT UN FRANCS CFA",
            80000: "QUATRE-VINGT MILLE FRANCS CFA",
            467704: "QUATRE CENT SOIXANTE-SEPT MILLE SEPT CENT QUATRE FRANCS CFA",
            800000: "HUIT CENT MILLE FRANCS CFA",
            2000000: "DEUX MILLIONS DE FRANCS CFA",
            55616535: "CINQUANTE-CINQ MILLIONS SIX CENT SEIZE MILLE CINQ CENT TRENTE-CINQ FRANCS CFA",
        }
        for montant, attendu in cas.items():
            self.assertEqual(montant_en_lettres(montant), attendu)

    def test_euro_et_dollar(self):
        self.assertEqual(montant_en_lettres(Decimal("1250.50"), "EUR"), "MILLE DEUX CENT CINQUANTE EUROS ET CINQUANTE CENTIMES")
        self.assertEqual(montant_en_lettres(Decimal("1.01"), "EUR"), "UN EURO ET UN CENTIME")
        self.assertEqual(montant_en_lettres(2000000, "USD"), "DEUX MILLIONS DE DOLLARS")
        self.assertEqual(montant_en_lettres(Decimal("80.80"), "USD"), "QUATRE-VINGTS DOLLARS ET QUATRE-VINGTS CENTS")


class SocleCommande(APITestCase):
    """Utilisateurs, demande validée et aides communes aux tests des bons de commande et de réception."""

    def setUp(self):
        def utilisateur(nom, role):
            u = Utilisateur.objects.create_user(nom, password="x", first_name=nom.capitalize())
            u.groups.add(Group.objects.get(name=role))
            return u

        self.demandeur = utilisateur("mecano", "Achats - Demandeur")
        self.chef = utilisateur("chef", "Achats - Demandeur")
        self.acheteur = utilisateur("acheteur", "Achats - Acheteur")
        self.autre_acheteur = utilisateur("acheteur2", "Achats - Acheteur")
        self.responsable = utilisateur("franck", "Achats - Responsable achats")
        self.controleur = utilisateur("cdg", "Achats - Contrôleur de gestion")
        Acheteur.objects.create(utilisateur=self.acheteur)
        self.service = Service.objects.get(code="TECH")
        self.service.responsable = self.chef
        self.service.save()
        self.site = Site.objects.get(code="SIEGE")
        self.fournisseur = Tiers.objects.create(code="516890", raison_sociale="ERIUM COTE D'IVOIRE", est_fournisseur=True,
                                                adresse="Treichville Bd", ville="ABIDJAN 01 BP 1753")
        self.demande = DemandeAchat.objects.create(demandeur=self.demandeur, service=self.service, site=self.site)
        self.demande.lignes.create(designation="Bouteille d'oxygène", quantite=3, unite=Unite.objects.get(code="U"))
        self.demande.soumettre(self.demandeur)
        self.demande.valider(self.chef)
        self.demande.valider(self.responsable)

    # Les lignes du bon de commande modèle : 396 359 HT, 71 345 de TVA, 467 704 TTC.
    LIGNES = [
        {"reference": "DIV 37446", "designation": "BOUTEILLE D'OXYGENE 7M3", "quantite": "3", "prix_unitaire": "39627"},
        {"reference": "DIV 37445", "designation": "BOUTEILLE D'ACETYLENE 6M3", "quantite": "2", "prix_unitaire": "112489"},
        {"reference": "ZIP PFRAIS", "designation": "LOCATION BOUTEILLE MENSUELLE", "quantite": "5", "prix_unitaire": "5500"},
        {"reference": "ZIP PFRAIS", "designation": "FRAIS DE LIVRAISON", "quantite": "5", "prix_unitaire": "5000"},
    ]

    def creer(self, par=None, **champs):
        self.client.force_authenticate(par or self.acheteur)
        donnees = {"demande": self.demande.id, "fournisseur": self.fournisseur.id, "site": self.site.id,
                   "service": self.service.id, "objet": "OXYGENE & ACETYLENE", "lignes": self.LIGNES, **champs}
        return self.client.post("/api/achats/bons-commande/", donnees, format="json")

    def agir(self, utilisateur, id, action, **donnees):
        self.client.force_authenticate(utilisateur)
        return self.client.post(f"/api/achats/bons-commande/{id}/{action}/", donnees, format="json")


class BonCommandeTests(SocleCommande):
    def test_totaux_identiques_au_bon_modele(self):
        r = self.creer()
        self.assertEqual(r.status_code, 201, r.data)
        t = r.data["totaux"]
        self.assertEqual((t["total_ht"], t["total_tva"], t["total_ttc"]), (Decimal(396359), Decimal(71345), Decimal(467704)))
        self.assertEqual(t["en_lettres"], "QUATRE CENT SOIXANTE-SEPT MILLE SEPT CENT QUATRE FRANCS CFA")
        self.assertTrue(r.data["numero"].startswith("BC-"))
        self.assertEqual(r.data["acheteur"], self.acheteur.id)

    def test_remise_et_taux_de_tva_par_ligne(self):
        r = self.creer(lignes=[
            {"designation": "A", "quantite": "2", "prix_unitaire": "1000", "remise": "10"},
            {"designation": "B", "quantite": "1", "prix_unitaire": "500", "taux_tva": "0"},
        ])
        t = r.data["totaux"]
        self.assertEqual((t["total_ht"], t["total_tva"], t["total_ttc"]), (Decimal(2300), Decimal(324), Decimal(2624)))
        self.assertEqual(len(t["ventilation"]), 2)

    def test_commande_en_euro_au_centime(self):
        r = self.creer(devise="EUR", lignes=[
            {"designation": "Vérin", "quantite": "3", "prix_unitaire": "149.99", "remise": "5"},
            {"designation": "Port", "quantite": "1", "prix_unitaire": "80.50", "taux_tva": "0"},
        ])
        self.assertEqual(r.status_code, 201, r.data)
        t = r.data["totaux"]
        # 149,99 - 5 % = 142,49 ; x3 = 427,47 ; TVA 18 % = 76,94 ; + 80,50 de port
        self.assertEqual((t["total_ht"], t["total_tva"], t["total_ttc"]), (Decimal("507.97"), Decimal("76.94"), Decimal("584.91")))
        self.assertEqual(t["en_lettres"], "CINQ CENT QUATRE-VINGT-QUATRE EUROS ET QUATRE-VINGT-ONZE CENTIMES")
        self.assertEqual(Decimal(r.data["taux_change"]), Decimal("655.957"))  # parité fixe, non saisie
        self.assertEqual(t["contre_valeur_xof"], Decimal(383676))
        self.client.force_authenticate(self.acheteur)
        self.assertTrue(self.client.get(f"/api/achats/bons-commande/{r.data['id']}/pdf/").content.startswith(b"%PDF"))

    def test_commande_en_dollar_exige_le_cours(self):
        ligne = [{"designation": "Pompe", "quantite": "2", "prix_unitaire": "1200.25"}]
        self.assertEqual(self.creer(devise="USD", lignes=ligne).status_code, 400)
        r = self.creer(devise="USD", taux_change="602.5", lignes=ligne)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["totaux"]["total_ht"], Decimal("2400.50"))
        self.assertEqual(r.data["totaux"]["contre_valeur_xof"], Decimal(1706635))  # 2 832,59 TTC x 602,5

    def test_activite(self):
        r = self.creer(activite="TRANSPORT")
        self.assertEqual(r.data["activite_libelle"], "Transport")
        r = self.creer(activite="AUTRE", activite_autre="Location de grue")
        self.assertEqual(r.data["activite_libelle"], "Location de grue")
        self.client.force_authenticate(self.acheteur)
        self.assertEqual(self.client.get("/api/achats/bons-commande/?activite=TRANSPORT").data["count"], 1)
        self.assertTrue(self.client.get(f"/api/achats/bons-commande/{r.data['id']}/pdf/").content.startswith(b"%PDF"))

    def test_signatures_imprimees_apres_les_deux_validations(self):
        import tempfile
        from unittest import mock

        from django.core.files.base import ContentFile
        from django.test import override_settings
        from PIL import Image as Pil

        from . import pdf

        with tempfile.TemporaryDirectory() as dossier, override_settings(MEDIA_ROOT=dossier):
            for u in (self.responsable, self.controleur):
                tampon = __import__("io").BytesIO()
                Pil.new("RGB", (300, 100), "white").save(tampon, "PNG")
                u.signature.save("signature.png", ContentFile(tampon.getvalue()))
                self.assertNotIn("signature.png", u.signature.name)  # nom imprévisible
            bon = self.creer().data
            url = f"/api/achats/bons-commande/{bon['id']}/pdf/"
            self.agir(self.acheteur, bon["id"], "soumettre")
            self.agir(self.responsable, bon["id"], "valider")
            with mock.patch.object(pdf, "Image", wraps=pdf.Image) as image:
                self.client.get(url)
                # une seule validation : aucune signature, seulement le logo
                self.assertEqual([a.args[0] for a in image.call_args_list if "signatures" in a.args[0]], [])
            self.agir(self.controleur, bon["id"], "valider")
            with mock.patch.object(pdf, "Image", wraps=pdf.Image) as image:
                self.assertTrue(self.client.get(url).content.startswith(b"%PDF"))
                signatures = [a.args[0] for a in image.call_args_list if "signatures" in a.args[0]]
                self.assertEqual(signatures, [self.responsable.signature.path, self.controleur.signature.path])

    def test_demande_non_validee_refusee(self):
        brouillon = DemandeAchat.objects.create(demandeur=self.demandeur, service=self.service, site=self.site)
        self.assertEqual(self.creer(demande=brouillon.id).status_code, 400)

    def test_tiers_non_fournisseur_refuse(self):
        client = Tiers.objects.create(code="C1", raison_sociale="Client", est_client=True)
        self.assertEqual(self.creer(fournisseur=client.id).status_code, 400)

    def test_le_demandeur_ne_cree_pas_de_bon(self):
        self.assertEqual(self.creer(par=self.demandeur).status_code, 403)

    def test_circuit_complet(self):
        bon = self.creer().data
        self.assertEqual(self.agir(self.acheteur, bon["id"], "soumettre").data["statut"], "ATT_RESP")
        # l'ordre des validations est imposé : le contrôleur ne peut pas passer avant le responsable achats
        self.assertEqual(self.agir(self.controleur, bon["id"], "valider").status_code, 403)
        self.assertEqual(self.agir(self.responsable, bon["id"], "valider").data["statut"], "ATT_CDG")
        self.assertEqual(self.agir(self.responsable, bon["id"], "valider").status_code, 403)
        r = self.agir(self.controleur, bon["id"], "valider")
        self.assertEqual(r.data["statut"], "VALIDE")
        self.assertTrue(r.data["definitif"])
        r = self.agir(self.acheteur, bon["id"], "transmettre")
        self.assertEqual(r.data["statut"], "TRANSMIS")
        self.assertIsNotNone(r.data["transmis_le"])

    def test_transmission_impossible_avant_les_deux_validations(self):
        bon = self.creer().data
        self.agir(self.acheteur, bon["id"], "soumettre")
        self.agir(self.responsable, bon["id"], "valider")
        self.assertEqual(self.agir(self.acheteur, bon["id"], "transmettre").status_code, 400)

    def test_refus_renvoie_a_l_acheteur_pour_correction(self):
        bon = self.creer().data
        self.agir(self.acheteur, bon["id"], "soumettre")
        self.agir(self.responsable, bon["id"], "valider")
        self.assertEqual(self.agir(self.controleur, bon["id"], "refuser").status_code, 400)
        r = self.agir(self.controleur, bon["id"], "refuser", commentaire="Mauvais service imputé")
        self.assertEqual(r.data["statut"], "BROUILLON")
        self.client.force_authenticate(self.acheteur)
        r = self.client.patch(f"/api/achats/bons-commande/{bon['id']}/", {"objet": "Corrigé"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        # après correction, le bon repasse par les deux validations
        self.assertEqual(self.agir(self.acheteur, bon["id"], "soumettre").data["statut"], "ATT_RESP")

    def test_bon_soumis_non_modifiable(self):
        bon = self.creer().data
        self.agir(self.acheteur, bon["id"], "soumettre")
        r = self.client.patch(f"/api/achats/bons-commande/{bon['id']}/", {"objet": "Autre"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_un_autre_acheteur_ne_modifie_pas_le_bon(self):
        bon = self.creer().data
        self.client.force_authenticate(self.autre_acheteur)
        r = self.client.patch(f"/api/achats/bons-commande/{bon['id']}/", {"objet": "Autre"}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.agir(self.autre_acheteur, bon["id"], "soumettre").status_code, 403)

    def test_annulation_reservee_au_responsable_avec_motif(self):
        bon = self.creer().data
        self.assertEqual(self.agir(self.acheteur, bon["id"], "annuler", commentaire="x").status_code, 403)
        self.assertEqual(self.agir(self.responsable, bon["id"], "annuler").status_code, 400)
        r = self.agir(self.responsable, bon["id"], "annuler", commentaire="Fournisseur en rupture")
        self.assertEqual(r.data["statut"], "ANNULE")

    def test_pdf(self):
        bon = self.creer().data
        self.client.force_authenticate(self.acheteur)
        r = self.client.get(f"/api/achats/bons-commande/{bon['id']}/pdf/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertTrue(r.content.startswith(b"%PDF"))
        self.client.force_authenticate(self.demandeur)
        self.assertEqual(self.client.get(f"/api/achats/bons-commande/{bon['id']}/pdf/").status_code, 403)

    def test_charge_de_l_acheteur_jusqu_au_bon_valide(self):
        def charge():
            return Acheteur.avec_charge().get(utilisateur=self.acheteur).en_cours

        self.assertEqual(charge(), 1)  # demande validée, pas encore de bon de commande
        bon = self.creer().data
        self.agir(self.acheteur, bon["id"], "soumettre")
        self.agir(self.responsable, bon["id"], "valider")
        self.assertEqual(charge(), 1)
        self.agir(self.controleur, bon["id"], "valider")
        self.assertEqual(charge(), 0)
