import io
from datetime import date
from unittest import mock

from django.contrib.auth.models import Group
from openpyxl import load_workbook

from apps.core.models import Utilisateur

from .tests_commande import SocleCommande


def lignes_du_classeur(reponse):
    return list(load_workbook(io.BytesIO(reponse.content)).active.iter_rows(values_only=True))


class ExportExcelTests(SocleCommande):
    def test_bons_de_commande_avec_les_filtres_de_l_ecran(self):
        self.assertEqual(self.creer().status_code, 201)
        self.client.force_authenticate(self.acheteur)
        r = self.client.get("/api/achats/bons-commande/exporter/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheetml", r["Content-Type"])
        self.assertIn("bons-commande-", r["Content-Disposition"])
        titres, ligne = lignes_du_classeur(r)
        self.assertEqual((titres[0], titres[2], titres[14]), ("N°", "Date", "Total TTC"))
        champs = dict(zip(titres, ligne))
        self.assertTrue(champs["N°"].startswith("BC-"))
        self.assertEqual((champs["Total HT"], champs["TVA"], champs["Total TTC"]), (396359, 71345, 467704))
        self.assertEqual((champs["Fournisseur"], champs["Devise"], champs["Statut"]), ("ERIUM COTE D'IVOIRE", "XOF", "Brouillon"))
        self.assertIsInstance(champs["Date"], (date,)) if not hasattr(champs["Date"], "date") else None
        # Le filtre de l'écran s'applique aussi à l'export : aucun bon validé.
        self.assertEqual(len(lignes_du_classeur(self.client.get("/api/achats/bons-commande/exporter/?statut=VALIDE"))), 1)

    def test_demandes_chacun_n_exporte_que_ce_qu_il_voit(self):
        self.client.force_authenticate(self.demandeur)
        self.assertEqual(len(lignes_du_classeur(self.client.get("/api/achats/demandes/exporter/"))), 2)   # titres + sa demande
        intrus = Utilisateur.objects.create_user("intrus", password="x")
        intrus.groups.add(Group.objects.get(name="Achats - Demandeur"))
        self.client.force_authenticate(intrus)
        self.assertEqual(len(lignes_du_classeur(self.client.get("/api/achats/demandes/exporter/"))), 1)  # titres seuls
        self.client.force_authenticate(self.acheteur)
        titres, ligne = lignes_du_classeur(self.client.get("/api/achats/demandes/exporter/"))
        self.assertEqual(dict(zip(titres, ligne))["Demandeur"], self.demandeur.first_name)

    def test_droits_et_limite(self):
        sans_droit = Utilisateur.objects.create_user("sansdroit", password="x")
        self.client.force_authenticate(sans_droit)
        self.assertEqual(self.client.get("/api/achats/bons-commande/exporter/").status_code, 403)
        self.client.force_authenticate(self.acheteur)
        with mock.patch("apps.core.export.LIMITE_LIGNES", 0):
            r = self.client.get("/api/achats/demandes/exporter/")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Précisez les filtres", str(r.data))
