import datetime
import io
import tempfile
from decimal import Decimal

from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.test import override_settings
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from rest_framework.test import APITestCase

from apps.core.models import Site, Utilisateur
from apps.referentiels.models import Tiers
from apps.technique.models import Materiel

from .models import Devis, ReglageCommercial

DEVIS = "/api/commercial/devis/"


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class DevisTests(APITestCase):
    def setUp(self):
        def utilisateur(nom, *roles):
            u = Utilisateur.objects.create_user(nom, password="x", first_name=nom.capitalize())
            u.groups.add(*Group.objects.filter(name__in=roles))
            return u

        self.commercial = utilisateur("vendeur", "Commercial - Commercial")
        self.collegue = utilisateur("collegue", "Commercial - Commercial")
        self.responsable = utilisateur("responsable", "Commercial - Responsable")
        self.lecteur = utilisateur("lecteur", "Commercial - Consultation")
        self.etranger = utilisateur("etranger", "Technique - Mécanicien")
        self.site = Site.objects.get(code="SIEGE")
        self.client_a = Tiers.objects.create(code="50100", raison_sociale="Client Essai", est_client=True, adresse="Zone 4", ville="Abidjan")
        self.fournisseur = Tiers.objects.create(code="F001", raison_sociale="Fournisseur", est_fournisseur=True)
        self.grue = Materiel.objects.create(code="GR-001", type="GRUE", designation="Grue mobile 50 t", site=self.site)

    def corps(self, **champs):
        return {"client": self.client_a.id, "libelle": "Mise à disposition d'un espace de stockage", "site": self.site.id,
                "type_loyer": "MOIS", "echeance": "60 JOURS NETS", "mode_reglement": "CHEQUE",
                "lignes": [{"designation": "Entrepôt de stockage 200 m2", "quantite": "1", "prix_unitaire": "800000", "duree": "1"}],
                **champs}

    def creer(self, par=None, **champs):
        self.client.force_authenticate(par or self.commercial)
        return self.client.post(DEVIS, self.corps(**champs), format="json")

    def agir(self, utilisateur, id, action, **donnees):
        self.client.force_authenticate(utilisateur)
        return self.client.post(f"{DEVIS}{id}/{action}/", donnees, format="json")

    def test_saisie_et_totaux(self):
        self.assertEqual(self.creer(par=self.lecteur).status_code, 403)
        self.assertEqual(self.creer(par=self.etranger).status_code, 403)
        self.assertEqual(self.creer(client=self.fournisseur.id).status_code, 400)
        r = self.creer(lignes=[
            {"designation": "Grue 50 t", "materiel": self.grue.id, "quantite": "1", "prix_unitaire": "350000", "remise": "10", "duree": "5"},
            {"designation": "Transport aller et retour", "quantite": "2", "prix_unitaire": "150000"}])
        self.assertEqual(r.status_code, 201, r.data)
        d = r.data
        self.assertRegex(d["numero"], r"^DV-\d{4}-0001$")
        self.assertEqual((d["statut"], d["commercial_nom"], d["lignes"][0]["materiel_nom"]), ("BROUILLON", "Vendeur", str(self.grue)))
        self.assertEqual(d["validite"], str(datetime.date.today() + datetime.timedelta(days=30)))
        self.assertEqual([Decimal(l["montant_ht"]) for l in d["lignes"]], [1575000, 300000])
        self.assertEqual(d["lignes"][1]["materiel_nom"], "")                           # ligne sans matériel du parc
        t = d["totaux"]
        self.assertEqual((t["total_ht"], t["total_tva"], t["total_ttc"]), (1875000, 337500, 2212500))
        self.assertIn("deux millions deux cent douze mille cinq cents", t["en_lettres"].lower())
        # client exonéré : pas de TVA ; les lignes se remplacent à la modification
        r = self.client.patch(f"{DEVIS}{d['id']}/", {"exonere_tva": True, "lignes": self.corps()["lignes"]}, format="json")
        self.assertEqual((len(r.data["lignes"]), r.data["totaux"]["total_tva"], r.data["totaux"]["total_ttc"]), (1, 0, 800000))
        # le devis d'un autre commercial ne se modifie pas, sauf par le responsable
        self.client.force_authenticate(self.collegue)
        self.assertEqual(self.client.patch(f"{DEVIS}{d['id']}/", {"libelle": "x"}, format="json").status_code, 403)
        self.client.force_authenticate(self.responsable)
        self.assertEqual(self.client.patch(f"{DEVIS}{d['id']}/", {"libelle": "Corrigé"}, format="json").status_code, 200)
        self.assertIn(self.client.delete(f"{DEVIS}{d['id']}/").status_code, (403, 405))
        self.assertEqual(self.creer(validite="2000-01-01").status_code, 400)

    def test_circuit(self):
        vide = self.creer(lignes=[]).data["id"]
        self.assertEqual(self.agir(self.commercial, vide, "envoyer").status_code, 400)       # aucune ligne
        id = self.creer().data["id"]
        self.assertEqual(self.agir(self.commercial, id, "accepter").status_code, 400)        # pas encore envoyé
        self.assertEqual(self.agir(self.collegue, id, "envoyer").status_code, 403)
        self.assertEqual(self.agir(self.lecteur, id, "envoyer").status_code, 403)
        self.assertEqual(self.agir(self.commercial, id, "envoyer").data["statut"], "ENVOYE")
        self.assertEqual(self.client.patch(f"{DEVIS}{id}/", {"libelle": "x"}, format="json").status_code, 400)   # figé
        # le client demande une retouche : reprise, modification, nouvel envoi
        self.assertEqual(self.agir(self.commercial, id, "reprendre").data["statut"], "BROUILLON")
        self.assertEqual(self.client.patch(f"{DEVIS}{id}/", {"echeance": "30 JOURS NETS"}, format="json").status_code, 200)
        self.agir(self.commercial, id, "envoyer")
        self.assertEqual(self.agir(self.commercial, id, "refuser").status_code, 400)         # motif obligatoire
        r = self.agir(self.commercial, id, "accepter", reference_client="BC-4471")
        self.assertEqual((r.data["statut"], r.data["reference_client"], r.data["accepte_le"]), ("ACCEPTE", "BC-4471", str(datetime.date.today())))
        # une commande acceptée ne s'annule que par le responsable
        self.assertEqual(self.agir(self.commercial, id, "annuler", motif="Erreur").status_code, 403)
        self.assertEqual(self.agir(self.responsable, id, "annuler", motif="Client en défaut").data["statut"], "ANNULE")
        autre = self.creer().data["id"]
        self.agir(self.commercial, autre, "envoyer")
        r = self.agir(self.commercial, autre, "refuser", motif="Trop cher")
        self.assertEqual((r.data["statut"], r.data["motif"]), ("REFUSE", "Trop cher"))

    def test_validite_depassee(self):
        id = self.creer().data["id"]
        self.agir(self.commercial, id, "envoyer")
        Devis.objects.filter(pk=id).update(date=datetime.date(2020, 1, 1), validite=datetime.date(2020, 1, 31))
        d = self.client.get(f"{DEVIS}{id}/").data
        self.assertEqual((d["expire"], d["statut_libelle"]), (True, "Envoyé, validité dépassée"))
        self.assertEqual(self.agir(self.commercial, id, "accepter").data["statut"], "ACCEPTE")   # le client peut encore signer

    def texte(self, id):
        r = self.client.get(f"{DEVIS}{id}/pdf/")
        self.assertEqual((r.status_code, r["Content-Type"]), (200, "application/pdf"))
        lecteur = PdfReader(io.BytesIO(r.content))
        return len(lecteur.pages), " ".join(p.extract_text() for p in lecteur.pages)

    def test_pdf(self):
        id = self.creer(date_retour="2026-11-08T18:00:00Z").data["id"]
        pages, texte = self.texte(id)
        self.assertEqual(pages, 1)
        for attendu in ("DEVIS N° DV-", "Client Essai", "N° Client : 50100", "MENSUEL", "60 JOURS NETS", "CHÈQUE", "800 000", "944 000",
                        "NEUF CENT QUARANTE-QUATRE MILLE FRANCS CFA", "PROJET", "NOTRE SIGNATURE"):
            self.assertIn(attendu, texte)
        self.agir(self.commercial, id, "envoyer")
        self.agir(self.commercial, id, "accepter", reference_client="BC-4471")
        # les conditions générales chargées dans l'administration suivent le devis
        annexe = io.BytesIO()
        c = canvas.Canvas(annexe)
        for page in ("CONDITIONS GENERALES DE LOCATION", "Suite des conditions"):
            c.drawString(100, 700, page)
            c.showPage()
        c.save()
        reglage = ReglageCommercial(extrait_conditions="EXTRAIT CGV LOCATION DE MATERIEL : nos locations...")
        reglage.conditions_generales.save("cgl.pdf", ContentFile(annexe.getvalue()))
        pages, texte = self.texte(id)
        self.assertEqual(pages, 3)
        for attendu in ("COMMANDE CLIENT N° DV-", "BC-4471", "EXTRAIT CGV", "CONDITIONS GENERALES DE LOCATION"):
            self.assertIn(attendu, texte)
        self.assertNotIn("PROJET", texte)
        reglage.conditions_generales.save("cgl.pdf", ContentFile(b"pas un pdf"))                # fichier abîmé : le devis sort quand même
        self.assertEqual(self.texte(id)[0], 1)
        reglage.conditions_generales.delete()
        self.client.force_authenticate(self.etranger)
        self.assertEqual(self.client.get(f"{DEVIS}{id}/pdf/").status_code, 403)
