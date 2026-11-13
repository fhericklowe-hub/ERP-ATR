import datetime

from django.contrib.auth.models import Group
from django.core import mail
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.core import rappels
from apps.core.models import Service, Site, Utilisateur

from .models import Contrat, PieceSalarie, Salarie

SALARIES = "/api/rh/salaries/"
CONTRATS = "/api/rh/contrats/"
PIECES = "/api/rh/pieces/"


class DossiersTests(APITestCase):
    def setUp(self):
        def utilisateur(nom, *roles, **champs):
            u = Utilisateur.objects.create_user(nom, password="x", first_name=nom.capitalize(), **champs)
            u.groups.add(*Group.objects.filter(name__in=roles))
            return u

        self.rh = utilisateur("gestionnaire", "RH - Gestionnaire", email="rh@example.com")
        self.lecteur = utilisateur("lecteur", "RH - Consultation", email="lecteur@example.com")
        self.etranger = utilisateur("etranger", "Achats - Responsable achats", "Stock - Responsable", "Commercial - Responsable")
        self.site = Site.objects.get(code="SIEGE")
        self.service = Service.objects.get(code="TECH")
        self.auj = timezone.localdate()
        self.client.force_authenticate(self.rh)

    def dans(self, jours):
        return str(self.auj + datetime.timedelta(days=jours))

    def creer(self, **champs):
        return self.client.post(SALARIES, {"nom": "essai", "prenoms": "Jean ", "site": self.site.id, **champs}, format="json")

    def test_dossier_et_confidentialite(self):
        r = self.creer(service=self.service.id, fonction="Cariste", categorie="OUVRIER", date_naissance="1990-05-01",
                       date_embauche=str(self.auj.replace(year=self.auj.year - 3) - datetime.timedelta(days=1)))
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data["matricule"], r.data["nom_complet"], r.data["statut"], r.data["anciennete"], r.data["contrat"]),
                         ("S0001", "ESSAI Jean", "ACTIF", 3, ""))
        self.assertEqual(r.data["responsable_nom"], "")
        id = r.data["id"]
        self.assertEqual(self.creer(matricule="A-12").data["matricule"], "A-12")
        self.assertEqual(self.creer(matricule="A-12").status_code, 400)                       # matricule déjà pris
        self.assertEqual(self.creer(date_naissance="2999-01-01").status_code, 400)
        self.assertEqual(self.creer(date_naissance="1990-01-01", date_embauche="1980-01-01").status_code, 400)
        self.assertEqual(self.client.patch(f"{SALARIES}{id}/", {"responsable": id}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(f"{SALARIES}{id}/", {"telephone": "0102030405"}, format="json").data["telephone"], "0102030405")
        self.assertIn(self.client.delete(f"{SALARIES}{id}/").status_code, (403, 405))
        self.assertEqual(self.client.get(SALARIES, {"search": "caris"}).data["count"], 1)
        self.assertEqual(self.client.get(f"{SALARIES}effectifs/").data["total"], 2)
        # consultation seule ; aucun autre rôle ne voit les dossiers, même un responsable d'un autre module
        self.client.force_authenticate(self.lecteur)
        self.assertEqual(self.client.get(f"{SALARIES}{id}/").data["peut_modifier"], False)
        self.assertEqual(self.client.patch(f"{SALARIES}{id}/", {"telephone": "x"}, format="json").status_code, 403)
        self.assertEqual(self.creer().status_code, 403)
        self.client.force_authenticate(self.etranger)
        for url in (SALARIES, f"{SALARIES}{id}/", f"{SALARIES}echeances/", f"{SALARIES}effectifs/", CONTRATS, PIECES):
            self.assertEqual(self.client.get(url).status_code, 403, url)
        self.assertIn(self.client.get("/api/pieces-jointes/", {"modele": "rh.salarie", "objet": id}).status_code, (403, 404))

    def test_contrats_et_sortie(self):
        id = self.creer(date_embauche="2024-01-15").data["id"]
        contrat = lambda **c: self.client.post(CONTRATS, {"salarie": id, **c}, format="json")  # noqa: E731
        self.assertEqual(contrat(type="CDD", date_debut="2024-01-15").status_code, 400)        # un CDD a une fin
        self.assertEqual(contrat(type="CDD", date_debut="2024-01-15", date_fin="2024-01-01").status_code, 400)
        self.assertEqual(contrat(type="CDI", date_debut="2025-01-15", fin_essai="2024-12-01").status_code, 400)
        cdd = contrat(type="CDD", date_debut="2024-01-15", date_fin="2025-01-14")
        self.assertEqual(cdd.status_code, 201, cdd.data)
        self.assertEqual(contrat(type="CDI", date_debut="2025-01-15", fonction="Cariste").status_code, 201)
        d = self.client.get(f"{SALARIES}{id}/").data
        self.assertEqual((d["contrat"], [c["type"] for c in d["contrats"]]), ("CDI", ["CDI", "CDD"]))
        self.assertEqual(self.client.patch(f"{CONTRATS}{cdd.data['id']}/", {"date_fin": "2023-01-01"}, format="json").status_code, 400)
        autre = self.creer(nom="Autre").data["id"]
        self.assertEqual(self.client.patch(f"{CONTRATS}{cdd.data['id']}/", {"salarie": autre}, format="json").status_code, 400)
        # sortie des effectifs
        sortir = lambda **c: self.client.post(f"{SALARIES}{id}/sortir/", c, format="json")     # noqa: E731
        self.assertEqual(sortir(motif="Démission").status_code, 400)
        self.assertEqual(sortir(date_sortie="2020-01-01", motif="Démission").status_code, 400)
        self.assertEqual(sortir(date_sortie=str(self.auj)).status_code, 400)
        self.client.force_authenticate(self.lecteur)
        self.assertEqual(sortir(date_sortie=str(self.auj), motif="Démission").status_code, 403)
        self.client.force_authenticate(self.rh)
        r = sortir(date_sortie=str(self.auj), motif="Démission")
        self.assertEqual((r.data["statut"], r.data["motif_sortie"]), ("SORTI", "Démission"))
        self.assertEqual(sortir(date_sortie=str(self.auj), motif="Démission").status_code, 400)
        self.assertEqual(self.client.get(SALARIES, {"statut": "ACTIF"}).data["count"], 1)
        self.assertEqual(self.client.post(f"{SALARIES}{id}/reintegrer/").data["statut"], "ACTIF")

    def test_echeances_et_rappel(self):
        a = Salarie.objects.create(nom="Alpha", prenoms="A", site=self.site, service=self.service)
        b = Salarie.objects.create(nom="Beta", prenoms="B", site=self.site)
        parti = Salarie.objects.create(nom="Parti", prenoms="P", site=self.site, statut="SORTI")
        piece = lambda s, type, jours, **c: PieceSalarie.objects.create(salarie=s, type=type, date_expiration=self.dans(jours), **c)  # noqa: E731
        piece(a, "PERMIS", -3, libelle="C")
        piece(a, "MEDICALE", 10)
        piece(a, "CONDUITE", -200, libelle="Chariot")
        piece(a, "CONDUITE", 300, libelle="Chariot")          # renouvelée : l'ancienne n'est plus signalée
        piece(b, "IDENTITE", 45)                              # au-delà de 30 jours
        piece(parti, "PERMIS", 5)                             # sorti des effectifs
        Contrat.objects.create(salarie=b, type="CDD", date_debut=self.dans(-300), date_fin=self.dans(20))
        Contrat.objects.create(salarie=a, type="CDI", date_debut=self.dans(-60), fin_essai=self.dans(25))
        r = self.client.get(f"{SALARIES}echeances/")
        self.assertEqual([(e["salarie_nom"], e["genre"], e["libelle"], e["jours"]) for e in r.data], [
            ("ALPHA A", "PIECE", "Permis de conduire C", -3), ("ALPHA A", "PIECE", "Visite médicale", 10),
            ("BETA B", "CONTRAT", "Fin du CDD", 20), ("ALPHA A", "ESSAI", "Fin de la période d'essai", 25)])
        self.assertEqual(len(self.client.get(f"{SALARIES}echeances/", {"jours": 60}).data), 5)
        self.assertEqual(len(self.client.get(f"{SALARIES}echeances/", {"service": self.service.id}).data), 3)
        self.assertEqual(self.client.get(f"{SALARIES}echeances/", {"jours": "x"}).status_code, 400)
        # CDD renouvelé : plus d'alerte
        Contrat.objects.create(salarie=b, type="CDI", date_debut=self.dans(21))
        self.assertEqual(len(self.client.get(f"{SALARIES}echeances/").data), 3)
        # rappel par e-mail : au gestionnaire seulement
        rappels.envoyer()
        self.assertEqual([m.to for m in mail.outbox], [["rh@example.com"]])
        self.assertIn("ALPHA A", mail.outbox[0].body)
        self.assertIn("Permis de conduire C", mail.outbox[0].body)
        self.assertIn("dépassé depuis 3 jour(s)", mail.outbox[0].body)
        # pièces : saisie contrôlée
        self.assertEqual(self.client.post(PIECES, {"salarie": a.id, "type": "PERMIS", "date_delivrance": "2026-01-01", "date_expiration": "2025-01-01"}, format="json").status_code, 400)
        r = self.client.post(PIECES, {"salarie": a.id, "type": "PERMIS", "libelle": "C", "date_expiration": self.dans(900)}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self.client.delete(f"{PIECES}{r.data['id']}/").status_code, 204)
