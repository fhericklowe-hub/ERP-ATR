from decimal import Decimal

from django.contrib.auth.models import Group
from rest_framework.test import APITestCase

from apps.core.models import Service, Utilisateur
from apps.referentiels.models import Article, Emplacement, Unite

from .models import BonSortie, Mouvement, quantite_en_stock

URL = "/api/stock/demandes/"


class DemandesSortieTests(APITestCase):
    def setUp(self):
        def utilisateur(nom, role):
            u = Utilisateur.objects.create_user(nom, password="x", first_name=nom.capitalize())
            u.groups.add(Group.objects.get(name=role))
            return u

        self.mecano = utilisateur("mecano", "Stock - Demandeur")
        self.chef = utilisateur("chef", "Stock - Demandeur")
        self.autre = utilisateur("autre", "Stock - Demandeur")
        self.magasinier = utilisateur("magasin", "Stock - Magasinier")
        self.service = Service.objects.get(code="TECH")
        self.service.responsable = self.chef
        self.service.save()
        self.sans_chef = Service.objects.get(code="COM")
        unite = Unite.objects.get(code="U")
        self.filtre = Article.objects.create(code="FIL-001", designation="Filtre à huile", unite=unite)
        self.papier = Article.objects.create(code="PAP-A4", designation="Rame de papier A4", unite=unite, nature="FOURN")
        self.siege = Emplacement.objects.get(type="SITE", site__code="SIEGE")
        for article, q in ((self.filtre, 5), (self.papier, 20)):
            Mouvement.objects.create(article=article, magasin=self.siege, type="INVENTAIRE", quantite=q, motif="Départ")

    def demander(self, lignes=None, par=None, **champs):
        self.client.force_authenticate(par or self.mecano)
        lignes = lignes if lignes is not None else {self.filtre: 2}
        donnees = {"service": self.service.id, "magasin": self.siege.id, "numero_or": "OR-77", "materiel": "Grue 3",
                   "lignes": [{"article": a.id, "quantite": str(q)} for a, q in lignes.items()], **champs}
        return self.client.post(URL, donnees, format="json")

    def agir(self, utilisateur, id, action, **donnees):
        self.client.force_authenticate(utilisateur)
        return self.client.post(f"{URL}{id}/{action}/", donnees, format="json")

    def stock(self, article=None):
        return quantite_en_stock(article or self.filtre, self.siege)

    def test_circuit_complet(self):
        r = self.demander()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data["numero"][:3], r.data["statut"]), ("DS-", "ATT_SERVICE"))
        id = r.data["id"]
        self.assertEqual(self.agir(self.magasinier, id, "servir").status_code, 403)   # pas avant la validation
        self.assertEqual(self.agir(self.mecano, id, "valider").status_code, 403)
        r = self.agir(self.chef, id, "valider")
        self.assertEqual((r.data["statut"], r.data["valide_par_nom"]), ("A_SERVIR", "Chef"))
        self.client.force_authenticate(self.magasinier)
        vue = self.client.get(f"{URL}{id}/").data
        self.assertEqual((vue["peut_servir"], Decimal(vue["lignes"][0]["en_stock"])), (True, 5))
        r = self.agir(self.magasinier, id, "servir")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data["statut"], Decimal(r.data["lignes"][0]["quantite_servie"])), ("SERVIE", 2))
        bon = BonSortie.objects.get()
        self.assertEqual((r.data["bon_sortie_numero"], bon.numero_or, bon.remis_a, bon.magasinier),
                         (bon.numero, "OR-77", self.mecano, self.magasinier))
        self.assertEqual(self.stock(), 3)
        self.assertEqual(self.agir(self.magasinier, id, "servir").status_code, 403)   # une seule fois

    def test_or_obligatoire_pour_une_piece_seulement(self):
        r = self.demander(numero_or="")
        self.assertEqual(r.status_code, 400)
        self.assertIn("OR", str(r.data))
        self.assertEqual(self.demander({self.papier: 3, self.filtre: 1}, numero_or=" ").status_code, 400)
        # Des fournitures de bureau, pour un service sans responsable : pas d'OR, et droit au magasin.
        r = self.demander({self.papier: 3}, numero_or="", service=self.sans_chef.id, motif="Bureau commercial")
        self.assertEqual((r.status_code, r.data["statut"]), (201, "A_SERVIR"))
        self.assertEqual(self.agir(self.magasinier, r.data["id"], "servir").status_code, 200)
        self.assertEqual((self.stock(self.papier), BonSortie.objects.get().numero_or), (17, ""))

    def test_le_responsable_demande_sans_se_valider(self):
        self.assertEqual(self.demander(par=self.chef).data["statut"], "A_SERVIR")

    def test_service_partiel(self):
        id = self.demander({self.filtre: 4, self.papier: 10}, par=self.chef).data["id"]
        self.client.force_authenticate(self.magasinier)
        lignes = {l["code"]: l["id"] for l in self.client.get(f"{URL}{id}/").data["lignes"]}
        trop = self.agir(self.magasinier, id, "servir", quantites={lignes["FIL-001"]: "5"})
        self.assertEqual(trop.status_code, 400)
        self.assertEqual(self.agir(self.magasinier, id, "servir", quantites={}).status_code, 400)
        r = self.agir(self.magasinier, id, "servir", quantites={lignes["FIL-001"]: "3"})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual({l["code"]: Decimal(l["quantite_servie"]) for l in r.data["lignes"]}, {"FIL-001": 3, "PAP-A4": 0})
        self.assertEqual((self.stock(), self.stock(self.papier), BonSortie.objects.get().lignes.count()), (2, 20, 1))

    def test_stock_insuffisant_au_moment_de_servir(self):
        id = self.demander({self.filtre: 9}, par=self.chef).data["id"]
        r = self.agir(self.magasinier, id, "servir")
        self.assertEqual(r.status_code, 400)
        self.assertIn("9 demandé pour 5 en stock", str(r.data))
        self.client.force_authenticate(self.magasinier)
        self.assertEqual(self.client.get(f"{URL}{id}/").data["statut"], "A_SERVIR")
        self.assertEqual((self.stock(), BonSortie.objects.count()), (5, 0))

    def test_refus_et_annulation(self):
        id = self.demander().data["id"]
        self.assertEqual(self.agir(self.chef, id, "refuser").status_code, 400)       # motif obligatoire
        self.assertEqual(self.agir(self.autre, id, "refuser", commentaire="x").status_code, 404)
        r = self.agir(self.chef, id, "refuser", commentaire="Déjà commandé")
        self.assertEqual((r.data["statut"], r.data["motif_refus"]), ("REFUSEE", "Déjà commandé"))
        id = self.demander(par=self.chef).data["id"]
        self.assertEqual(self.agir(self.magasinier, id, "annuler", commentaire="x").status_code, 403)
        self.assertEqual(self.agir(self.chef, id, "annuler", commentaire="Erreur").data["statut"], "ANNULEE")
        self.assertEqual(self.agir(self.magasinier, id, "servir").status_code, 403)
        id = self.demander(par=self.chef).data["id"]
        self.assertEqual(self.agir(self.magasinier, id, "refuser", commentaire="Article réservé").data["statut"], "REFUSEE")
        self.assertEqual(self.stock(), 5)

    def test_visibilite(self):
        id = self.demander().data["id"]
        self.demander(par=self.autre, service=self.sans_chef.id)

        def vues(u):
            self.client.force_authenticate(u)
            return self.client.get(URL).data["count"]

        self.assertEqual([vues(u) for u in (self.mecano, self.chef, self.autre, self.magasinier)], [1, 1, 1, 2])
        self.client.force_authenticate(self.autre)
        self.assertEqual(self.client.get(f"{URL}{id}/").status_code, 404)
        self.assertIsNone(self.client.get(URL).data["results"][0]["lignes"][0]["en_stock"])

    def test_demandes_refusees(self):
        self.assertEqual(self.demander({}).status_code, 400)
        self.assertEqual(self.demander({self.filtre: 0}).status_code, 400)
        service = Article.objects.create(code="SRV", designation="Prestation", unite=Unite.objects.get(code="U"),
                                         nature="SERVICE", gere_en_stock=False)
        self.assertEqual(self.demander({service: 1}).status_code, 400)
        sans_role = Utilisateur.objects.create_user("visiteur", password="x")
        self.assertEqual(self.demander(par=sans_role).status_code, 403)
