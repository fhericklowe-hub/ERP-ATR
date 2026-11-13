import datetime
from decimal import Decimal
from io import BytesIO

from django.utils import timezone
from openpyxl import load_workbook

from .models import Mouvement
from . import tests as socle

MOUVEMENTS = socle.MOUVEMENTS
VALEUR = "/api/stock/valeur/"
CONSOMMATIONS = "/api/stock/consommations/"


class ValorisationTests(socle.StockTests):
    for _nom in [n for n in dir(socle.StockTests) if n.startswith("test_")]:
        locals()[_nom] = None       # on reprend le socle, pas ses tests

    def entrer(self, quantite, prix, article=None, magasin=None):
        """Ajustement chiffré : quantité ajoutée au prix donné."""
        self.client.force_authenticate(self.chef_stock)
        r = self.client.post(f"{MOUVEMENTS}ajuster/", {
            "article": (article or self.filtre).id, "magasin": (magasin or self.siege).id,
            "quantite": str(self.stock(article, magasin) + quantite), "motif": "Entrée", **({"prix_unitaire": str(prix)} if prix else {})}, format="json")
        self.assertEqual(r.status_code, 201, r.data)

    def valeur(self, par=None, **filtres):
        self.client.force_authenticate(par or self.chef_stock)
        return self.client.get(VALEUR, filtres)

    def test_cout_moyen_pondere(self):
        self.entrer(10, 4000)
        self.entrer(10, 5000)                                   # coût moyen : 4 500
        self.assertEqual(self.sortir({self.filtre: 4}).status_code, 201)       # sortie à 4 500, reste 16
        self.entrer(4, 7000)                                    # (16 × 4 500 + 4 × 7 000) / 20 = 5 000
        self.entrer(5, None)                                    # sans prix : entre au coût moyen
        self.client.force_authenticate(self.chef_stock)
        r = self.client.post(f"{MOUVEMENTS}transferer/", {"article": self.filtre.id, "origine": self.siege.id,
                                                          "destination": self.marcory.id, "quantite": "5"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.entrer(3, None, article=self.courroie)             # jamais chiffrée
        d = self.valeur().data
        self.assertEqual([(l["code"], l["magasin_nom"], l["quantite"], l["cout_moyen"], l["valeur"]) for l in d["results"]], [
            ("COU-001", self.siege.nom, Decimal(3), None, None),
            ("FIL-001", self.marcory.nom, Decimal(5), Decimal("5000.00"), Decimal(25000)),
            ("FIL-001", self.siege.nom, Decimal(20), Decimal("5000.00"), Decimal(100000))])
        self.assertEqual((d["total"], d["sans_prix"]), (Decimal(125000), 1))
        self.assertEqual(self.valeur(magasin=self.marcory.id).data["total"], Decimal(25000))
        self.assertEqual(self.valeur(search="courroie").data["count"], 1)
        # réception par bon de commande : 5 filtres à 4 500
        self.recevoir()
        self.assertEqual(self.valeur().data["total"], Decimal(147500))        # 30 filtres à 4 916,67
        # consommations du mois : 4 filtres à 4 500, par service et par OR
        c = self.client.get(CONSOMMATIONS).data
        self.assertEqual((c["total"], c["par_or"]), (Decimal(18000), [{"numero_or": "OR-2026-0412", "materiel": "Chariot 12", "valeur": Decimal(18000)}]))
        self.assertEqual(c["par_service"], [{"service": "Sans service", "valeur": Decimal(18000)}])
        # une sortie annulée ne compte plus
        bon = self.sortir({self.filtre: 2}).data
        self.client.force_authenticate(self.chef_stock)
        self.assertGreater(self.client.get(CONSOMMATIONS).data["total"], Decimal(18000))
        self.client.force_authenticate(self.chef_stock)
        self.assertEqual(self.client.post(f"/api/stock/sorties/{bon['id']}/annuler/", {"commentaire": "Erreur"}, format="json").status_code, 200)
        self.assertEqual(self.client.get(CONSOMMATIONS).data["total"], Decimal(18000))

    def test_valeur_a_une_date_et_export(self):
        self.entrer(10, 4000)
        Mouvement.objects.update(date=timezone.now() - datetime.timedelta(days=40))
        self.entrer(10, 6000)
        hier = timezone.localdate() - datetime.timedelta(days=1)
        self.assertEqual(self.valeur(date=str(hier)).data["total"], Decimal(40000))
        self.assertEqual(self.valeur().data["total"], Decimal(100000))
        self.assertEqual(self.valeur(date="2999-01-01").status_code, 400)
        self.assertEqual(self.valeur(date="hier").status_code, 400)
        r = self.valeur(export="xlsx")
        self.assertEqual(r.status_code, 200)
        lignes = list(load_workbook(BytesIO(r.content)).active.values)
        self.assertEqual(lignes[3][:1] + lignes[3][5:], ("FIL-001", 20, 5000, 100000))
        self.assertEqual(lignes[-1][6:], ("Total", 100000))
        self.assertEqual(self.client.get(CONSOMMATIONS, {"debut": "2026-02-01", "fin": "2026-01-01"}).status_code, 400)

    def test_reserve_a_ceux_qui_voient_les_montants(self):
        self.entrer(10, 4000)
        for utilisateur, attendu in ((self.magasinier, 403), (self.lecteur, 403), (self.demandeur, 403), (self.controleur, 200),
                                     (self.responsable, 200), (self.chef_stock, 200)):
            self.assertEqual(self.valeur(par=utilisateur).status_code, attendu, utilisateur)
            self.assertEqual(self.client.get(CONSOMMATIONS).status_code, attendu, utilisateur)
