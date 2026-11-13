import datetime

from django.contrib.auth.models import Group
from django.core import mail
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.core import rappels
from apps.core.models import Site, Utilisateur
from apps.rh.models import Salarie

from .models import ActionCorrective, Evenement

VISITES = "/api/hse/visites/"
ACTIONS = "/api/hse/actions/"
EPI = "/api/hse/epi/"


class TerrainTests(APITestCase):
    def setUp(self):
        def compte(nom, *roles, **champs):
            u = Utilisateur.objects.create_user(nom, password="x", first_name=nom.capitalize(), **champs)
            u.groups.add(*Group.objects.filter(name__in=roles))
            return u

        self.hse = compte("hse", "HSE - Responsable", email="hse@example.com")
        self.chef = compte("chef", "HSE - Visiteur", email="chef@example.com")
        self.autre = compte("autre", "HSE - Visiteur")
        self.agent = compte("agent", "HSE - Déclarant", email="agent@example.com")
        self.etranger = compte("etranger", "Achats - Demandeur")
        self.site = Site.objects.get(code="SIEGE")
        self.aujourd_hui = timezone.localdate()

    def jour(self, n):
        return str(self.aujourd_hui + datetime.timedelta(days=n))

    def agir(self, par, url, methode="post", **donnees):
        self.client.force_authenticate(par)
        return getattr(self.client, methode)(url, donnees, format="json")

    def visiter(self, par=None, **champs):
        return self.agir(par or self.chef, VISITES, site=self.site.id, lieu="Atelier mécanique",
                         **{"ecarts": "Extincteur masqué par des palettes.", **champs})

    def test_visite_actions_et_cloture(self):
        r = self.visiter(points_positifs="Port du casque respecté.", participants="Chef d'atelier")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertRegex(r.data["numero"], r"^VS-\d{4}-0001$")
        self.assertEqual((r.data["statut"], r.data["visiteur_nom"], r.data["statut_libelle"]), ("OUVERTE", "Chef", "À clore"))
        id, url = r.data["id"], f"{VISITES}{r.data['id']}/"
        self.assertEqual(self.visiter(ecarts="").status_code, 400)                           # aucun constat
        self.assertEqual(self.visiter(date=self.jour(1)).status_code, 400)
        self.assertEqual(self.visiter(par=self.agent).status_code, 403)
        self.assertEqual(self.visiter(par=self.etranger).status_code, 403)
        # visibilité : le visiteur, le responsable HSE, et plus tard le responsable d'une action
        self.assertEqual(self.agir(self.autre, VISITES, "get").data["count"], 0)
        self.assertEqual(self.agir(self.autre, url, "patch", lieu="x").status_code, 404)
        self.assertEqual(self.agir(self.agent, VISITES, "get").data["count"], 0)
        self.assertEqual(self.agir(self.etranger, VISITES, "get").status_code, 403)
        self.assertEqual(self.agir(self.hse, VISITES, "get").data["count"], 1)
        self.assertEqual(self.agir(self.chef, url, "patch", lieu="Atelier, zone soudure").data["lieu"], "Atelier, zone soudure")
        self.assertEqual(self.agir(self.chef, url, "patch", ecarts="").status_code, 200)        # il reste un point positif
        self.assertEqual(self.agir(self.chef, url, "patch", points_positifs="").status_code, 400)
        # actions : le visiteur pour sa visite, le responsable HSE partout
        action = {"visite": id, "description": "Dégager l'extincteur", "responsable": self.agent.id, "echeance": self.jour(2)}
        self.assertEqual(self.agir(self.autre, ACTIONS, **action).status_code, 403)
        self.assertEqual(self.agir(self.agent, ACTIONS, **action).status_code, 403)
        a1 = self.agir(self.chef, ACTIONS, **action)
        self.assertEqual(a1.status_code, 201, a1.data)
        self.assertEqual((a1.data["visite_numero"], a1.data["evenement_numero"]), (r.data["numero"], ""))
        a2 = self.agir(self.hse, ACTIONS, **{**action, "description": "Marquer la zone au sol", "responsable": self.chef.id}).data
        self.assertEqual(self.agir(self.chef, ACTIONS, **{k: v for k, v in action.items() if k != "visite"}).status_code, 400)
        evenement = Evenement.objects.create(type="DANGER", date=timezone.now(), site=self.site, description="x", declarant=self.chef)
        self.assertEqual(self.agir(self.chef, ACTIONS, **action, evenement=evenement.id).status_code, 400)   # les deux
        self.assertEqual(self.agir(self.chef, ACTIONS, **{**action, "visite": None, "evenement": evenement.id}).status_code, 403)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ActionCorrective.objects.create(description="x", responsable=self.chef, echeance=self.aujourd_hui)
        self.assertEqual(self.agir(self.chef, f"{ACTIONS}?visite={id}", "get").data["count"], 2)
        self.assertEqual(self.agir(self.chef, f"{ACTIONS}?miennes=1", "get").data["count"], 1)
        # le responsable d'une action voit la visite et termine son action
        vue = self.agir(self.agent, url, "get")
        self.assertEqual((vue.status_code, vue.data["actions_a_faire"], vue.data["peut_modifier"], vue.data["statut_libelle"]),
                         (200, 2, False, "Actions en cours"))
        self.assertEqual(self.agir(self.agent, url, "patch", lieu="x").status_code, 403)
        rappels.envoyer()
        corps = {m.to[0]: m.body for m in mail.outbox}
        self.assertIn(f"{r.data['numero']} : Dégager l'extincteur", corps["agent@example.com"])
        # clôture
        self.assertEqual(self.agir(self.chef, f"{url}clore/").status_code, 403)
        self.assertEqual(self.agir(self.hse, f"{url}clore/").status_code, 400)                  # actions à faire
        self.assertEqual(self.agir(self.agent, f"{ACTIONS}{a1.data['id']}/terminer/").data["statut"], "FAITE")
        self.assertEqual(self.agir(self.chef, f"{ACTIONS}{a2['id']}/terminer/", commentaire="Peinture posée").data["statut"], "FAITE")
        clos = self.agir(self.hse, f"{url}clore/")
        self.assertEqual((clos.data["statut"], clos.data["statut_libelle"]), ("CLOSE", "Close"))
        self.assertEqual(self.agir(self.hse, f"{url}clore/").status_code, 400)
        self.assertEqual(self.agir(self.chef, url, "patch", lieu="x").status_code, 403)
        self.assertEqual(self.agir(self.hse, ACTIONS, **action).status_code, 400)
        self.assertIn(self.agir(self.hse, url, "delete").status_code, (403, 405))
        self.assertEqual(self.agir(self.chef, f"{url}rouvrir/").status_code, 403)
        self.assertEqual(self.agir(self.hse, f"{url}rouvrir/").data["statut"], "OUVERTE")
        # photos de la visite
        self.assertEqual(self.agir(self.chef, f"/api/pieces-jointes/?modele=hse.visite&objet={id}", "get").status_code, 200)
        self.assertIn(self.agir(self.autre, f"/api/pieces-jointes/?modele=hse.visite&objet={id}", "get").status_code, (403, 404))

    def test_epi(self):
        def salarie(nom, **champs):
            return Salarie.objects.create(nom=nom, prenoms="Test", site=self.site, date_embauche=datetime.date(2020, 1, 6), **champs)

        s1, s2 = salarie("ALPHA"), salarie("BETA")
        parti = salarie("GAMMA")
        Salarie.objects.filter(pk=parti.pk).update(statut="SORTI")
        # le responsable HSE voit la liste réduite des salariés, pas leur dossier
        self.assertEqual(self.agir(self.chef, f"{EPI}salaries/", "get").status_code, 403)
        liste = self.agir(self.hse, f"{EPI}salaries/", "get").data
        self.assertEqual([(x["nom"], x["matricule"]) for x in liste], [("ALPHA Test", s1.matricule), ("BETA Test", s2.matricule)])
        self.assertEqual(set(liste[0]), {"id", "nom", "matricule", "site_nom"})
        self.assertEqual(self.agir(self.hse, "/api/rh/salaries/", "get").status_code, 403)

        def remettre(par=None, **champs):
            return self.agir(par or self.hse, EPI, **{"salarie": s1.id, "equipement": "CHAUSSURES", "precision": "Pointure 43", **champs})

        r = remettre(date_remise=self.jour(-200), a_renouveler_le=self.jour(-10))
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data["salarie_nom"], r.data["remis_par_nom"], r.data["jours"], r.data["quantite"]), ("ALPHA Test", "Hse", -10, 1))
        self.assertEqual(remettre(par=self.chef).status_code, 403)
        self.assertEqual(remettre(salarie=parti.id).status_code, 400)
        self.assertEqual(remettre(date_remise=self.jour(1)).status_code, 400)
        self.assertEqual(remettre(a_renouveler_le=self.jour(-1)).status_code, 400)
        self.assertEqual(remettre(quantite=0).status_code, 400)
        remettre(equipement="CASQUE", a_renouveler_le=self.jour(20))
        remettre(equipement="GANTS", a_renouveler_le=self.jour(90))
        remettre(equipement="GILET")
        remettre(salarie=s2.id, equipement="HARNAIS", a_renouveler_le=self.jour(5))

        def a_renouveler(jours=""):
            return [(x["salarie_nom"], x["equipement"]) for x in self.agir(self.hse, f"{EPI}renouvellements/{jours}", "get").data]

        self.assertEqual(a_renouveler(), [("ALPHA Test", "CHAUSSURES"), ("BETA Test", "HARNAIS"), ("ALPHA Test", "CASQUE")])
        self.assertEqual(len(a_renouveler("?jours=120")), 4)
        self.assertEqual(self.agir(self.hse, f"{EPI}renouvellements/?jours=x", "get").status_code, 400)
        self.assertEqual(self.agir(self.hse, f"{EPI}?salarie={s1.id}", "get").data["count"], 4)
        self.assertEqual(self.agir(self.hse, f"{EPI}?search=beta", "get").data["count"], 1)
        rappels.envoyer()
        corps = {m.to[0]: m.body for m in mail.outbox}["hse@example.com"]
        self.assertIn("chaussures de sécurité", corps)
        self.assertIn("(dépassé)", corps)
        self.assertNotIn("gants", corps)
        # une nouvelle paire remise : l'ancienne n'est plus signalée ; un salarié sorti non plus
        remettre(a_renouveler_le=self.jour(300))
        Salarie.objects.filter(pk=s2.pk).update(statut="SORTI")
        self.assertEqual(a_renouveler(), [("ALPHA Test", "CASQUE")])
        # correction et suppression d'une saisie
        url = f"{EPI}{r.data['id']}/"
        self.assertEqual(self.agir(self.hse, url, "patch", precision="Pointure 44").data["precision"], "Pointure 44")
        self.assertEqual(self.agir(self.hse, url, "patch", salarie=s2.id).status_code, 400)
        self.assertEqual(self.agir(self.hse, url, "delete").status_code, 204)
