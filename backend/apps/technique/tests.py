import datetime
from decimal import Decimal

from django.contrib.auth.models import Group
from rest_framework.test import APITestCase

from apps.core.models import Site, Utilisateur
from apps.referentiels.models import Article, Emplacement, Unite
from apps.stock.models import BonSortie, Mouvement

from .models import Materiel, ReglageAtelier

MATERIELS = "/api/technique/materiels/"
ORDRES = "/api/technique/ordres/"
PLANS = "/api/technique/plans/"


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

    # ----- temps passé et coûts

    def test_temps_passe(self):
        id = self.ouvrir().data["id"]
        self.assertEqual(self.agir(self.mecano, id, "saisir_temps", heures="2").status_code, 400)   # pas encore démarré
        self.agir(self.mecano, id, "demarrer")
        self.assertEqual(self.agir(self.lecteur, id, "saisir_temps", heures="2").status_code, 403)
        self.assertEqual(self.agir(self.mecano, id, "saisir_temps", heures="0").status_code, 400)
        self.assertEqual(self.agir(self.mecano, id, "saisir_temps", heures="2", date="2999-01-01").status_code, 400)
        r = self.agir(self.mecano, id, "saisir_temps", heures="2.5", commentaire="Dépose du mât")
        self.assertEqual([(t["mecanicien_nom"], t["heures"]) for t in r.data["temps"]], [(str(self.mecano), "2.50")])
        # un collègue aide et saisit ses heures, mais pas celles d'un autre ; le chef saisit pour tous
        self.assertEqual(self.agir(self.collegue, id, "saisir_temps", heures="1").status_code, 200)
        self.assertEqual(self.agir(self.collegue, id, "saisir_temps", heures="1", mecanicien=self.mecano.id).status_code, 403)
        r = self.agir(self.chef, id, "saisir_temps", heures="3", mecanicien=self.mecano.id)
        self.assertEqual(len(r.data["temps"]), 3)
        self.assertEqual(self.agir(self.chef, id, "saisir_temps", heures="20", mecanicien=self.mecano.id).status_code, 400)
        # chacun retire sa saisie, le chef toutes ; plus rien après la clôture
        la_mienne, du_collegue = r.data["temps"][0]["id"], r.data["temps"][1]["id"]
        self.assertEqual(self.agir(self.mecano, id, "retirer_temps", temps=du_collegue).status_code, 403)
        self.assertEqual(len(self.agir(self.mecano, id, "retirer_temps", temps=la_mienne).data["temps"]), 2)
        self.agir(self.mecano, id, "terminer", travaux="Fait")
        self.assertEqual(self.agir(self.mecano, id, "saisir_temps", heures="1").status_code, 200)  # oubli rattrapé
        self.agir(self.chef, id, "cloturer")
        self.assertEqual(self.agir(self.chef, id, "saisir_temps", heures="1").status_code, 400)
        self.assertEqual(self.agir(self.chef, id, "retirer_temps", temps=du_collegue).status_code, 400)

    def test_cout_de_l_ordre(self):
        ordre = self.ouvrir().data
        id = ordre["id"]
        self.agir(self.mecano, id, "demarrer")
        self.agir(self.mecano, id, "saisir_temps", heures="1")                       # avant tout taux : non chiffrée
        ReglageAtelier.objects.create(taux_horaire=Decimal("3000"))
        self.agir(self.mecano, id, "saisir_temps", heures="2.5")
        ReglageAtelier.objects.update(taux_horaire=Decimal("9999"))                  # ne touche pas les heures saisies
        unite = Unite.objects.get(code="U")
        flexible = Article.objects.create(code="FLX-01", designation="Flexible hydraulique", unite=unite)
        joint = Article.objects.create(code="JNT-01", designation="Joint", unite=unite)
        magasin = Emplacement.objects.get(type="SITE", site=self.site)
        Mouvement.objects.create(article=flexible, magasin=magasin, type="INVENTAIRE", quantite=5, prix_unitaire=Decimal("10000"))
        Mouvement.objects.create(article=flexible, magasin=magasin, type="INVENTAIRE", quantite=5, prix_unitaire=Decimal("12000"))
        Mouvement.objects.create(article=joint, magasin=magasin, type="INVENTAIRE", quantite=5)   # prix inconnu
        BonSortie.enregistrer(self.magasinier, [(flexible, Decimal(2)), (joint, Decimal(1))], magasin=magasin,
                              numero_or=ordre["numero"], remis_a=self.mecano)
        self.client.force_authenticate(self.chef)
        d = self.client.get(f"{ORDRES}{id}/").data
        c = d["couts"]
        self.assertEqual((c["heures"], c["main_oeuvre"], c["pieces"], c["total"]),
                         (Decimal("3.5"), Decimal("7500"), Decimal("24000"), Decimal("31500")))
        self.assertEqual((c["heures_non_chiffrees"], c["pieces_sans_prix"]), (Decimal("1"), 1))
        self.assertEqual([p["montant"] for p in d["pieces"]], [Decimal("24000"), None])
        # le mécanicien voit les heures et les pièces, pas les montants
        self.client.force_authenticate(self.mecano)
        d = self.client.get(f"{ORDRES}{id}/").data
        self.assertIsNone(d["couts"])
        self.assertEqual({p["prix_unitaire"] for p in d["pieces"]} | {t["montant"] for t in d["temps"]}, {None})
        self.assertEqual(len(d["temps"]), 2)

    # ----- entretien préventif

    def plan(self, **champs):
        self.client.force_authenticate(self.chef)
        return self.client.post(PLANS, {"materiel": self.chariot.id, "intitule": "Vidange moteur", **champs}, format="json")

    def test_plan_d_entretien_par_compteur(self):
        self.assertEqual(self.plan().status_code, 400)                              # aucune périodicité
        self.client.force_authenticate(self.mecano)
        self.assertEqual(self.client.post(PLANS, {"materiel": self.chariot.id, "intitule": "x", "intervalle_mois": 6},
                                          format="json").status_code, 403)
        p = self.plan(intervalle_heures="250").data                                # part du compteur actuel : 4200 h
        self.assertEqual((p["dernier_heures"], p["prochaines_heures"], p["situation"]), ("4200.0", "4450.0", "A_VENIR"))
        lire = lambda: self.client.get(f"{PLANS}{p['id']}/").data
        self.chariot.compteur_heures = Decimal("4430")
        self.chariot.save()
        self.assertEqual(lire()["situation"], "PROCHE")
        self.chariot.compteur_heures = Decimal("4460")
        self.chariot.save()
        self.assertEqual((lire()["situation"], lire()["restes"]), ("RETARD", [{"reste": "-10.0", "unite": "h"}]))
        # le mécanicien ouvre l'OR d'entretien ; un seul à la fois ; le matériel n'est pas immobilisé
        r = self.client.post(f"{PLANS}{p['id']}/ouvrir_ordre/")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.client.post(f"{PLANS}{p['id']}/ouvrir_ordre/").status_code, 400)
        ordre = self.client.get(f"{ORDRES}{r.data['id']}/").data
        self.assertEqual((ordre["type"], ordre["immobilisant"], ordre["plan_intitule"]), ("PREVENTIF", False, "Vidange moteur"))
        self.assertEqual((self.etat(), lire()["ordre_en_cours"]["numero"]), ("DISPONIBLE", ordre["numero"]))
        # la fin des travaux repousse l'échéance à partir du compteur relevé
        self.agir(self.mecano, ordre["id"], "demarrer")
        self.agir(self.mecano, ordre["id"], "terminer", travaux="Vidange faite", compteur_heures="4465")
        d = lire()
        self.assertEqual((d["dernier_heures"], d["prochaines_heures"], d["situation"], d["ordre_en_cours"]),
                         ("4465.0", "4715.0", "A_VENIR", None))
        self.assertEqual(d["dernier_le"], str(datetime.date.today()))

    def test_plan_d_entretien_par_date(self):
        il_y_a = lambda jours: str(datetime.date.today() - datetime.timedelta(days=jours))
        self.assertEqual(self.plan(intervalle_mois=6, dernier_le="2999-01-01").status_code, 400)
        self.assertEqual(self.plan(intervalle_mois=6, dernier_le=il_y_a(30)).data["situation"], "A_VENIR")
        self.assertEqual(self.plan(intervalle_mois=6, dernier_le=il_y_a(175)).data["situation"], "PROCHE")
        p = self.plan(intervalle_mois=6, intervalle_km=10000, dernier_le=il_y_a(200)).data   # le premier atteint l'emporte
        self.assertEqual((p["situation"], p["dernier_km"], p["prochain_km"]), ("RETARD", 0, 10000))
        # un plan abandonné ne s'ouvre plus
        self.client.patch(f"{PLANS}{p['id']}/", {"actif": False}, format="json")
        self.assertEqual(self.client.post(f"{PLANS}{p['id']}/ouvrir_ordre/").status_code, 400)
        self.assertEqual(self.client.patch(f"{PLANS}{p['id']}/", {"intervalle_mois": None, "intervalle_km": None},
                                           format="json").status_code, 400)
        self.assertIn(self.client.delete(f"{PLANS}{p['id']}/").status_code, (403, 405))
