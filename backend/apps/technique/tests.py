from decimal import Decimal

from django.contrib.auth.models import Group
from rest_framework.test import APITestCase

from apps.core.models import Site, Utilisateur
from apps.referentiels.models import Article, Emplacement, Unite
from apps.stock.models import BonSortie, Mouvement

from .models import Materiel

MATERIELS = "/api/technique/materiels/"
ORDRES = "/api/technique/ordres/"


class TechniqueTests(APITestCase):
    def setUp(self):
        def utilisateur(nom, *roles):
            u = Utilisateur.objects.create_user(nom, password="x", first_name=nom.capitalize())
            u.groups.add(*Group.objects.filter(name__in=roles))
            return u

        self.chef = utilisateur("chef", "Technique - Chef d'atelier")
        self.mecano = utilisateur("mecano", "Technique - Mécanicien")
        self.collegue = utilisateur("collegue", "Technique - Mécanicien")
        self.lecteur = utilisateur("lecteur", "Technique - Consultation")
        self.magasinier = utilisateur("magasin", "Stock - Magasinier")
        self.site = Site.objects.get(code="SIEGE")
        self.chariot = Materiel.objects.create(code="CH-012", type="CHARIOT", designation="Chariot 3,5 t", site=self.site,
                                               compteur_heures=Decimal("4200"))

    def ouvrir(self, par=None, **champs):
        self.client.force_authenticate(par or self.mecano)
        return self.client.post(ORDRES, {"materiel": self.chariot.id, "description": "Fuite hydraulique au mât", **champs},
                                format="json")

    def agir(self, utilisateur, id, action, **donnees):
        self.client.force_authenticate(utilisateur)
        return self.client.post(f"{ORDRES}{id}/{action}/", donnees, format="json")

    def etat(self):
        self.chariot.refresh_from_db()
        return self.chariot.etat

    # ----- parc

    def test_parc_reserve_au_chef_d_atelier(self):
        fiche = {"code": "GR-003", "type": "GRUE", "designation": "Grue mobile 50 t", "site": self.site.id, "activite": "LEVAGE"}
        self.client.force_authenticate(self.mecano)
        self.assertEqual(self.client.post(MATERIELS, fiche, format="json").status_code, 403)
        self.client.force_authenticate(self.chef)
        r = self.client.post(MATERIELS, fiche, format="json")
        self.assertEqual((r.status_code, r.data["etat"], r.data["activite_libelle"]), (201, "DISPONIBLE", "Levage"))
        self.assertEqual(self.client.post(MATERIELS, fiche, format="json").status_code, 400)   # n° de parc unique
        self.assertIn(self.client.delete(f"{MATERIELS}{r.data['id']}/").status_code, (403, 405))
        self.client.force_authenticate(self.lecteur)
        self.assertEqual(self.client.get(MATERIELS, {"search": "grue"}).data["count"], 1)
        self.client.force_authenticate(self.magasinier)
        self.assertEqual(self.client.get(MATERIELS).status_code, 403)

    # ----- ordres de réparation

    def test_circuit_complet(self):
        r = self.ouvrir()
        self.assertEqual(r.status_code, 201, r.data)
        id = r.data["id"]
        self.assertEqual((r.data["numero"][:3], r.data["statut"], r.data["demandeur_nom"]), ("OR-", "OUVERT", "Mecano"))
        self.assertEqual(self.etat(), "EN_PANNE")
        r = self.agir(self.mecano, id, "demarrer", diagnostic="Flexible percé", compteur_heures="4215.5")
        self.assertEqual((r.data["statut"], r.data["mecanicien_nom"], r.data["diagnostic"]), ("EN_COURS", "Mecano", "Flexible percé"))
        self.assertEqual(self.etat(), "REPARATION")
        self.assertEqual(self.chariot.compteur_heures, Decimal("4215.5"))
        self.assertEqual(self.agir(self.mecano, id, "terminer").status_code, 400)        # travaux à décrire
        r = self.agir(self.mecano, id, "terminer", travaux="Flexible remplacé, niveau refait")
        self.assertEqual(r.data["statut"], "TERMINE")
        self.assertEqual(self.etat(), "DISPONIBLE")
        self.assertEqual(self.agir(self.mecano, id, "cloturer").status_code, 403)
        r = self.agir(self.chef, id, "cloturer")
        self.assertEqual((r.data["statut"], r.data["cloture_par_nom"]), ("CLOTURE", "Chef"))
        self.client.force_authenticate(self.mecano)
        self.assertEqual(self.client.patch(f"{ORDRES}{id}/", {"description": "x"}, format="json").status_code, 400)
        r = self.agir(self.chef, id, "rouvrir", commentaire="La fuite est revenue")
        self.assertEqual(r.data["statut"], "EN_COURS")
        self.assertEqual(self.etat(), "REPARATION")

    def test_affectation(self):
        id = self.ouvrir(par=self.chef).data["id"]
        self.assertEqual(self.agir(self.mecano, id, "affecter", mecanicien=self.mecano.id).status_code, 403)
        self.assertEqual(self.agir(self.chef, id, "affecter", mecanicien=self.collegue.id).data["mecanicien_nom"], "Collegue")
        self.assertEqual(self.agir(self.mecano, id, "demarrer").status_code, 403)       # confié à un autre
        self.assertEqual(self.agir(self.lecteur, id, "demarrer").status_code, 403)
        self.assertEqual(self.agir(self.magasinier, id, "demarrer").status_code, 403)
        self.assertEqual(self.agir(self.collegue, id, "demarrer").data["statut"], "EN_COURS")
        self.assertEqual(self.agir(self.chef, id, "terminer", travaux="Fait").data["statut"], "TERMINE")

    def test_entretien_sans_immobilisation(self):
        id = self.ouvrir(type="PREVENTIF", immobilisant=False, description="Vidange des 500 h").data["id"]
        self.assertEqual(self.etat(), "DISPONIBLE")
        self.agir(self.mecano, id, "demarrer")
        self.assertEqual(self.etat(), "DISPONIBLE")

    def test_deux_ordres_sur_le_meme_materiel(self):
        a = self.ouvrir().data["id"]
        b = self.ouvrir(description="Pneu avant usé").data["id"]
        self.agir(self.mecano, a, "demarrer")
        self.agir(self.mecano, a, "terminer", travaux="Fait")
        self.assertEqual(self.etat(), "EN_PANNE")                # le second ordre immobilise encore le chariot
        self.assertEqual(self.agir(self.mecano, b, "annuler", commentaire="x").status_code, 403)
        self.assertEqual(self.agir(self.chef, b, "annuler").status_code, 400)
        self.assertEqual(self.agir(self.chef, b, "annuler", commentaire="Doublon").data["statut"], "ANNULE")
        self.assertEqual(self.etat(), "DISPONIBLE")

    def test_materiel_reforme(self):
        self.chariot.etat = "REFORME"
        self.chariot.save()
        self.assertEqual(self.ouvrir().status_code, 400)

    def test_pieces_sorties_du_stock(self):
        ordre = self.ouvrir().data
        filtre = Article.objects.create(code="FLX-01", designation="Flexible hydraulique", unite=Unite.objects.get(code="U"))
        magasin = Emplacement.objects.get(type="SITE", site=self.site)
        Mouvement.objects.create(article=filtre, magasin=magasin, type="INVENTAIRE", quantite=5, motif="Départ")
        BonSortie.enregistrer(self.magasinier, [(filtre, Decimal(2))], magasin=magasin, numero_or=ordre["numero"].lower(),
                              remis_a=self.mecano)
        self.client.force_authenticate(self.mecano)
        pieces = self.client.get(f"{ORDRES}{ordre['id']}/").data["pieces"]
        self.assertEqual([(p["code"], Decimal(p["quantite"])) for p in pieces], [("FLX-01", 2)])
        self.assertEqual(self.client.get(ORDRES).data["results"][0]["pieces"], [])
        r = self.agir(self.chef, ordre["id"], "annuler", commentaire="Erreur")
        self.assertEqual(r.status_code, 400)
        self.assertIn("pièces", str(r.data))

    def test_liste_des_ordres_ouverts(self):
        a = self.ouvrir().data["id"]
        self.ouvrir()
        self.agir(self.mecano, a, "demarrer")
        self.agir(self.mecano, a, "terminer", travaux="Fait")
        self.client.force_authenticate(self.lecteur)
        self.assertEqual((self.client.get(ORDRES).data["count"], self.client.get(ORDRES, {"ouvert": 1}).data["count"]), (2, 1))
        self.assertEqual(self.ouvrir(par=self.lecteur).status_code, 403)
