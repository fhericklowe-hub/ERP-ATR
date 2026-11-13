from apps.core.models import Utilisateur

from . import tests_commande as socle
from .models import DemandeAchat


class AccueilTests(socle.SocleCommande):
    def rubriques(self, utilisateur):
        self.client.force_authenticate(utilisateur)
        r = self.client.get("/api/accueil/")
        self.assertEqual(r.status_code, 200)
        return {x["titre"]: x for x in r.data}

    def test_chacun_voit_ce_qui_l_attend(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/accueil/").status_code, 401)
        # une nouvelle demande attend le responsable du service, puis les achats
        d = DemandeAchat.objects.create(demandeur=self.demandeur, service=self.service, site=self.site)
        d.lignes.create(designation="Filtre", quantite=1, unite=self.demande.lignes.first().unite)
        d.soumettre(self.demandeur)
        titre = "Demandes d'achat à traiter"
        attente = self.rubriques(self.chef)[titre]
        self.assertEqual((attente["nombre"], attente["lien"]), (1, "/"))
        self.assertIn(d.numero, attente["lignes"][0])
        self.assertNotIn(titre, self.rubriques(self.demandeur))
        self.assertNotIn(titre, self.rubriques(self.responsable))
        d.valider(self.chef)
        self.assertNotIn(titre, self.rubriques(self.chef))
        self.assertIn(titre, self.rubriques(self.responsable))
        self.assertIn(titre, self.rubriques(self.acheteur))              # elle lui est attribuée
        self.assertNotIn(titre, self.rubriques(self.autre_acheteur))
        # un bon de commande attend le responsable achats, puis le contrôleur de gestion
        id = self.creer().data["id"]
        titre = "Bons de commande à valider"
        self.assertNotIn(titre, self.rubriques(self.responsable))        # encore en brouillon
        self.assertEqual(self.agir(self.acheteur, id, "soumettre").status_code, 200)
        self.assertEqual(self.rubriques(self.responsable)[titre]["lien"], "/commandes")
        self.assertNotIn(titre, self.rubriques(self.controleur))
        self.assertEqual(self.agir(self.responsable, id, "valider").status_code, 200)
        self.assertNotIn(titre, self.rubriques(self.responsable))
        self.assertEqual(self.rubriques(self.controleur)[titre]["nombre"], 1)
        # un compte sans rôle n'a rien
        self.assertEqual(self.rubriques(Utilisateur.objects.create_user("nouveau", password="x")), {})
