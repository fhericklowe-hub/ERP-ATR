from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook

from apps.achats.tests_commande import SocleCommande
from apps.core.models import Utilisateur
from apps.referentiels.models import Article, Emplacement, Unite

from .models import BonSortie, Mouvement, ReglageStock, quantite_en_stock

ETAT = "/api/stock/etat/"
SORTIES = "/api/stock/sorties/"
MOUVEMENTS = "/api/stock/mouvements/"


class StockTests(SocleCommande):
    def setUp(self):
        super().setUp()

        def utilisateur(nom, *roles):
            u = Utilisateur.objects.create_user(nom, password="x", first_name=nom.capitalize())
            u.groups.add(*Group.objects.filter(name__in=roles))
            return u

        self.magasinier = utilisateur("magasin", "Achats - Magasinier", "Stock - Magasinier")
        self.chef_stock = utilisateur("chefstock", "Stock - Responsable")
        self.lecteur = utilisateur("lecteur", "Stock - Consultation")
        unite = Unite.objects.get(code="U")
        self.filtre = Article.objects.create(code="FIL-001", designation="Filtre à huile", unite=unite)
        self.courroie = Article.objects.create(code="COU-001", designation="Courroie", unite=unite)
        self.prestation = Article.objects.create(code="SRV-001", designation="Main d'œuvre", unite=unite,
                                                 nature="SERVICE", gere_en_stock=False)
        self.siege = Emplacement.objects.get(type="SITE", site=self.site)
        self.marcory = Emplacement.objects.get(type="SITE", site__code="MARCORY")

    # ----- aides

    def stock(self, article=None, magasin=None):
        return quantite_en_stock(article or self.filtre, magasin or self.siege)

    def ajuster(self, quantite, par=None, article=None, magasin=None, motif="Stock de départ"):
        self.client.force_authenticate(par or self.chef_stock)
        return self.client.post(f"{MOUVEMENTS}ajuster/", {
            "article": (article or self.filtre).id, "magasin": (magasin or self.siege).id, "quantite": str(quantite),
            "motif": motif}, format="json")

    def sortir(self, lignes, par=None, **champs):
        """lignes : {article: quantité}"""
        self.client.force_authenticate(par or self.magasinier)
        donnees = {"magasin": self.siege.id, "numero_or": "OR-2026-0412", "materiel": "Chariot 12",
                   "remis_a": self.demandeur.id, "lignes": [{"article": a.id, "quantite": str(q)} for a, q in lignes.items()],
                   **champs}
        return self.client.post(SORTIES, donnees, format="json")

    def recevoir(self, **champs):
        """Commande de 10 filtres (article du catalogue) et d'une ligne libre, reçue : 6 filtres, dont 5 en stock."""
        lignes = [{"article": self.filtre.id, "designation": "Filtre à huile", "quantite": "10", "prix_unitaire": "4500"},
                  {"designation": "Frais de livraison", "quantite": "1", "prix_unitaire": "5000"}]
        bon = self.creer(lignes=lignes).data
        for utilisateur, action in ((self.acheteur, "soumettre"), (self.responsable, "valider"),
                                    (self.controleur, "valider"), (self.acheteur, "transmettre")):
            self.agir(utilisateur, bon["id"], action)
        self.client.force_authenticate(self.magasinier)
        recu = [{"ligne_commande": bon["lignes"][0]["id"], "quantite_recue": "6", "quantite_stock": "5"},
                {"ligne_commande": bon["lignes"][1]["id"], "quantite_recue": "1", "quantite_stock": "1"}]
        r = self.client.post("/api/achats/bons-reception/", {"commande": bon["id"], "lignes": recu, **champs}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        return self.client.post(f"/api/achats/bons-reception/{r.data['id']}/valider/", {}, format="json")

    # ----- entrées par les réceptions

    def test_reception_validee_entre_en_stock(self):
        r = self.recevoir()
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["magasin"], self.siege.id)  # par défaut, le site de la commande
        self.assertEqual(self.stock(), 5)
        entree = Mouvement.objects.get()  # la ligne libre, sans article du catalogue, n'entre pas en stock
        self.assertEqual((entree.type, entree.prix_unitaire, entree.auteur), ("RECEPTION", Decimal(4500), self.magasinier))
        self.assertIn(r.data["numero"], entree.motif)

    def test_reception_dans_un_autre_magasin(self):
        self.recevoir(magasin=self.marcory.id)
        self.assertEqual((self.stock(), self.stock(magasin=self.marcory)), (0, 5))

    def test_annuler_la_reception_ressort_le_stock(self):
        br = self.recevoir().data
        self.client.force_authenticate(self.responsable)
        r = self.client.post(f"/api/achats/bons-reception/{br['id']}/annuler/", {"commentaire": "Erreur"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self.stock(), 0)
        self.assertEqual(Mouvement.objects.count(), 2)

    def test_annulation_refusee_si_les_pieces_sont_sorties(self):
        br = self.recevoir().data
        self.assertEqual(self.sortir({self.filtre: 4}).status_code, 201)
        self.client.force_authenticate(self.responsable)
        r = self.client.post(f"/api/achats/bons-reception/{br['id']}/annuler/", {"commentaire": "Erreur"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("déjà sorti", str(r.data))
        self.client.force_authenticate(self.magasinier)
        self.assertEqual(self.client.get(f"/api/achats/bons-reception/{br['id']}/").data["statut"], "VALIDE")
        self.assertEqual(self.stock(), 1)

    # ----- sorties

    def test_sortie_avec_or(self):
        self.ajuster(10)
        self.ajuster(3, article=self.courroie)
        r = self.sortir({self.filtre: 4, self.courroie: 1})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["numero"], f"BS-{r.data['date'][:4]}-0001")
        self.assertEqual((r.data["numero_or"], r.data["magasinier_nom"], len(r.data["lignes"])), ("OR-2026-0412", "Magasin", 2))
        self.assertEqual((self.stock(), self.stock(self.courroie)), (6, 2))

    def test_pas_de_sortie_sans_or(self):
        self.ajuster(10)
        for numero in ("", "   "):
            r = self.sortir({self.filtre: 1}, numero_or=numero)
            self.assertEqual(r.status_code, 400)
            self.assertIn("OR", str(r.data))
        r = self.client.post(SORTIES, {"magasin": self.siege.id, "remis_a": self.demandeur.id,
                                       "lignes": [{"article": self.filtre.id, "quantite": "1"}]}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual((self.stock(), BonSortie.objects.count()), (10, 0))

    def test_pas_de_sortie_au_dela_du_stock(self):
        self.ajuster(2)
        self.ajuster(5, article=self.courroie)
        r = self.sortir({self.courroie: 1, self.filtre: 3})
        self.assertEqual(r.status_code, 400)
        self.assertIn("3 demandé pour 2 en stock", str(r.data))
        # Rien n'est sorti, même la ligne qui était possible, et le numéro n'est pas consommé.
        self.assertEqual((self.stock(), self.stock(self.courroie), BonSortie.objects.count()), (2, 5, 0))
        self.assertEqual(self.sortir({self.filtre: 2}).data["numero"][-4:], "0001")
        # Le stock de Marcory ne sert pas au siège.
        self.ajuster(9, magasin=self.marcory)
        self.assertEqual(self.sortir({self.filtre: 1}).status_code, 400)

    def test_sorties_refusees(self):
        self.ajuster(10)
        self.assertEqual(self.sortir({}).status_code, 400)
        self.assertEqual(self.sortir({self.filtre: 0}).status_code, 400)
        self.assertEqual(self.sortir({self.prestation: 1}).status_code, 400)
        self.assertEqual(self.sortir({self.filtre: 1}, par=self.lecteur).status_code, 403)
        self.assertEqual(self.sortir({self.filtre: 1}, par=self.demandeur).status_code, 403)
        doublon = {"magasin": self.siege.id, "numero_or": "OR-1", "remis_a": self.demandeur.id,
                   "lignes": [{"article": self.filtre.id, "quantite": "1"}] * 2}
        self.client.force_authenticate(self.magasinier)
        self.assertEqual(self.client.post(SORTIES, doublon, format="json").status_code, 400)
        self.assertEqual(self.stock(), 10)

    def test_annuler_une_sortie(self):
        self.ajuster(10)
        bon = self.sortir({self.filtre: 4}).data
        annuler = f"{SORTIES}{bon['id']}/annuler/"
        self.assertEqual(self.client.post(annuler, {"commentaire": "Erreur"}, format="json").status_code, 403)
        self.client.force_authenticate(self.chef_stock)
        self.assertEqual(self.client.post(annuler, {}, format="json").status_code, 400)
        r = self.client.post(annuler, {"commentaire": "Mauvais OR"}, format="json")
        self.assertEqual((r.data["statut"], r.data["motif_annulation"]), ("ANNULE", "Mauvais OR"))
        self.assertEqual(self.stock(), 10)
        self.assertEqual(self.client.post(annuler, {"commentaire": "x"}, format="json").status_code, 400)
        # Un bon de sortie ne se modifie pas et ne se supprime pas.
        self.assertEqual(self.client.patch(f"{SORTIES}{bon['id']}/", {"numero_or": "X"}, format="json").status_code, 405)
        self.assertIn(self.client.delete(f"{SORTIES}{bon['id']}/").status_code, (403, 405))

    # ----- inventaire, transfert, état

    def test_ajustement_d_inventaire(self):
        self.assertEqual(self.ajuster(10).status_code, 201)
        r = self.ajuster(7, motif="Inventaire de novembre")
        self.assertEqual((r.data["type"], Decimal(r.data["quantite"])), ("INVENTAIRE", Decimal(-3)))
        self.assertEqual(self.stock(), 7)
        self.assertEqual(self.ajuster(7).status_code, 400)       # déjà à cette quantité
        self.assertEqual(self.ajuster(-1).status_code, 400)
        self.assertEqual(self.ajuster(5, motif=" ").status_code, 400)
        self.assertEqual(self.ajuster(5, article=self.prestation).status_code, 400)
        self.assertEqual(self.ajuster(5, par=self.magasinier).status_code, 403)
        self.assertEqual(self.stock(), 7)

    def test_transfert(self):
        self.ajuster(10)
        self.client.force_authenticate(self.chef_stock)
        corps = {"article": self.filtre.id, "origine": self.siege.id, "destination": self.marcory.id, "quantite": "4"}
        self.assertEqual(self.client.post(f"{MOUVEMENTS}transferer/", corps, format="json").status_code, 201)
        self.assertEqual((self.stock(), self.stock(magasin=self.marcory)), (6, 4))
        self.assertEqual(self.client.post(f"{MOUVEMENTS}transferer/", {**corps, "quantite": "7"}, format="json").status_code, 400)
        self.assertEqual(self.client.post(f"{MOUVEMENTS}transferer/", {**corps, "destination": self.siege.id}, format="json").status_code, 400)
        self.client.force_authenticate(self.magasinier)
        self.assertEqual(self.client.post(f"{MOUVEMENTS}transferer/", corps, format="json").status_code, 403)
        self.assertEqual((self.stock(), self.stock(magasin=self.marcory)), (6, 4))

    def test_etat_du_stock_et_alerte(self):
        self.ajuster(10)
        self.ajuster(2, article=self.courroie)
        self.ajuster(1, magasin=self.marcory)
        self.client.force_authenticate(self.chef_stock)
        r = self.client.post("/api/stock/reglages/", {"article": self.courroie.id, "magasin": self.siege.id,
                                                      "seuil_mini": "3", "casier": "A-12"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.client.force_authenticate(self.lecteur)
        etat = self.client.get(ETAT).data
        self.assertEqual((etat["count"], etat["peut_ajuster"], etat["peut_sortir"]), (3, False, False))
        self.assertEqual([(l["code"], l["magasin_nom"], Decimal(l["quantite"])) for l in etat["results"]],
                         [("COU-001", self.siege.nom, 2), ("FIL-001", self.marcory.nom, 1), ("FIL-001", self.siege.nom, 10)])
        alertes = self.client.get(ETAT, {"alerte": 1}).data["results"]
        self.assertEqual([(l["code"], l["casier"]) for l in alertes], [("COU-001", "A-12")])
        self.assertEqual(self.client.get(ETAT, {"magasin": self.marcory.id}).data["count"], 1)
        self.assertEqual(self.client.get(ETAT, {"search": "courr"}).data["count"], 1)
        self.assertEqual(self.client.get(MOUVEMENTS, {"article": self.filtre.id}).data["count"], 2)
        self.client.force_authenticate(self.demandeur)
        self.assertEqual(self.client.get(ETAT).status_code, 403)
        self.assertEqual(self.client.get(MOUVEMENTS).status_code, 403)

    # ----- PDF et import

    def test_pdf_du_bon_de_sortie(self):
        self.ajuster(10)
        bon = self.sortir({self.filtre: 2}).data
        r = self.client.get(f"{SORTIES}{bon['id']}/pdf/")
        self.assertEqual((r.status_code, r["Content-Type"]), (200, "application/pdf"))
        self.assertTrue(r.content.startswith(b"%PDF"))
        self.client.force_authenticate(self.demandeur)
        self.assertEqual(self.client.get(f"{SORTIES}{bon['id']}/pdf/").status_code, 403)

    def classeur(self, lignes, titres=("Code", "Désignation", "Unité", "Quantité", "Seuil", "Rangement", "Prix")):
        wb = Workbook()
        wb.active.append(titres)
        for ligne in lignes:
            wb.active.append(ligne)
        tampon = BytesIO()
        wb.save(tampon)
        return SimpleUploadedFile("stock.xlsx", tampon.getvalue())

    def importer(self, lignes, par=None, **champs):
        self.client.force_authenticate(par or self.chef_stock)
        return self.client.post(f"{MOUVEMENTS}importer/", {"fichier": self.classeur(lignes, **champs.pop("classeur", {})),
                                                           "magasin": self.siege.id, **champs}, format="multipart")

    LIGNES = [("FIL-001", "Filtre à huile", "U", 12, 4, "A-12", 4500), ("NEUF-9", "Roulement 6204", "u", "3,5", None, None, None),
              (None, None, None, None, None, None, None)]

    def test_import_du_stock(self):
        self.ajuster(2)
        simulation = self.importer(self.LIGNES, simuler="1")
        self.assertEqual(simulation.status_code, 200, simulation.data)
        self.assertEqual((simulation.data["lues"], simulation.data["articles_crees"], simulation.data["ecrit"]), (2, 1, False))
        self.assertEqual((self.stock(), Article.objects.filter(code="NEUF-9").count()), (2, 0))
        r = self.importer(self.LIGNES)
        self.assertEqual((r.data["stocks_modifies"], r.data["articles_crees"], r.data["erreurs"], r.data["ecrit"]), (2, 1, [], True))
        neuf = Article.objects.get(code="NEUF-9")
        self.assertEqual((self.stock(), self.stock(neuf)), (12, Decimal("3.5")))
        reglage = ReglageStock.objects.get(article=self.filtre, magasin=self.siege)
        self.assertEqual((reglage.seuil_mini, reglage.casier), (4, "A-12"))
        # Le même fichier une seconde fois ne change rien.
        r = self.importer(self.LIGNES)
        self.assertEqual((r.data["stocks_modifies"], r.data["inchanges"], r.data["articles_crees"]), (0, 2, 0))

    def test_import_refuse_en_bloc(self):
        r = self.importer([("FIL-001", "Filtre", "U", 5, None, None, None), ("X-1", "Sans quantité", "U", None, None, None, None),
                           ("X-2", "Unité inconnue", "PALETTE", 1, None, None, None), ("fil-001", "Doublon", "U", 1, None, None, None),
                           ("SRV-001", "Service", "U", 1, None, None, None), ("X-3", "Négatif", "U", -2, None, None, None)])
        self.assertEqual(r.status_code, 200)
        self.assertEqual((len(r.data["erreurs"]), r.data["ecrit"]), (5, False))
        self.assertIn("Ligne 3", r.data["erreurs"][0])
        self.assertEqual((self.stock(), Mouvement.objects.count(), Article.objects.filter(code__startswith="X-").count()), (0, 0, 0))
        self.assertEqual(self.importer([("A", 1)], classeur={"titres": ("Code", "Quantité")}).status_code, 400)
        self.assertEqual(self.importer(self.LIGNES, par=self.magasinier).status_code, 403)
        self.client.force_authenticate(self.chef_stock)
        pas_excel = SimpleUploadedFile("stock.xlsx", b"ceci n'est pas un classeur")
        self.assertEqual(self.client.post(f"{MOUVEMENTS}importer/", {"fichier": pas_excel, "magasin": self.siege.id},
                                          format="multipart").status_code, 400)
