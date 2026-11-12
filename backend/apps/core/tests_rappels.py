import datetime
from decimal import Decimal

from django.contrib.auth.models import Group
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.core import rappels
from apps.core.models import Site, Utilisateur
from apps.moyens.contrats import Echeance
from apps.referentiels.models import Article, Emplacement, Unite
from apps.stock.models import Mouvement, ReglageStock
from apps.technique.models import Materiel, PlanEntretien


@override_settings(ADRESSE_ERP="https://erp.exemple.test")
class RappelsTests(TestCase):
    def setUp(self):
        def utilisateur(nom, *roles, email=True):
            u = Utilisateur.objects.create_user(nom, password="x", first_name=nom.capitalize(), email=f"{nom}@exemple.test" if email else "")
            u.groups.add(*Group.objects.filter(name__in=roles))
            return u

        self.gestionnaire = utilisateur("gestion", "Moyens généraux - Gestionnaire")
        self.chef = utilisateur("chef", "Technique - Chef d'atelier", "Stock - Responsable")
        self.mecano = utilisateur("mecano", "Technique - Mécanicien")
        self.sans_adresse = utilisateur("muet", "Moyens généraux - Gestionnaire", email=False)
        Utilisateur.objects.create_superuser("admin", "admin@exemple.test", "x")    # compte technique sans rôle
        aujourdhui, site = datetime.date.today(), Site.objects.get(code="SIEGE")
        jour = lambda n: aujourdhui + datetime.timedelta(days=n)
        Echeance.objects.create(type="ASSURANCE", libelle="Assurance flotte", date_echeance=jour(-3))
        Echeance.objects.create(type="VISITE", libelle="Visite technique camion", date_echeance=jour(10), rappel_jours=30)
        Echeance.objects.create(type="AUTRE", libelle="Lointaine", date_echeance=jour(200))
        Echeance.objects.create(type="AUTRE", libelle="Déjà faite", date_echeance=jour(-10), statut="FAITE")
        chariot = Materiel.objects.create(code="CH-012", type="CHARIOT", designation="Chariot", site=site, compteur_heures=Decimal("500"))
        PlanEntretien.objects.create(materiel=chariot, intitule="Vidange", intervalle_heures=250, dernier_heures=200, dernier_le=aujourdhui)
        PlanEntretien.objects.create(materiel=chariot, intitule="Graissage", intervalle_mois=6, dernier_le=aujourdhui)
        filtre = Article.objects.create(code="FIL-01", designation="Filtre à huile", unite=Unite.objects.get(code="U"))
        huile = Article.objects.create(code="HUI-01", designation="Huile moteur", unite=Unite.objects.get(code="U"))
        magasin = Emplacement.objects.get(type="SITE", site=site)
        Mouvement.objects.create(article=filtre, magasin=magasin, type="INVENTAIRE", quantite=2)
        Mouvement.objects.create(article=huile, magasin=magasin, type="INVENTAIRE", quantite=50)
        ReglageStock.objects.create(article=filtre, magasin=magasin, seuil_mini=5)
        ReglageStock.objects.create(article=huile, magasin=magasin, seuil_mini=10)

    def test_chacun_recoit_ce_qui_le_concerne(self):
        envoyes = dict(rappels.envoyer())
        self.assertEqual({u.username: n for u, n in envoyes.items()}, {"gestion": 2, "chef": 2})
        messages = {m.to[0]: m for m in mail.outbox}
        self.assertEqual(set(messages), {"gestion@exemple.test", "chef@exemple.test"})
        gestion = messages["gestion@exemple.test"]
        self.assertEqual(gestion.subject, "ERP : 2 point(s) à traiter")
        self.assertIn("Assurance flotte : en retard de 3 jour(s)", gestion.body)
        self.assertIn("Visite technique camion", gestion.body)
        self.assertNotIn("Lointaine", gestion.body)
        self.assertNotIn("Déjà faite", gestion.body)
        self.assertNotIn("Vidange", gestion.body)
        self.assertIn("https://erp.exemple.test", gestion.body)
        chef = messages["chef@exemple.test"].body
        self.assertIn("CH-012 · Vidange : à faire", chef)
        self.assertNotIn("Graissage", chef)
        self.assertIn("Filtre à huile (FIL-01) à Siège : 2 en stock, seuil 5", chef)
        self.assertNotIn("Huile moteur", chef)
        self.assertNotIn("Assurance", chef)

    def test_un_entretien_deja_lance_n_est_plus_rappele(self):
        PlanEntretien.objects.get(intitule="Vidange").ouvrir_ordre(self.chef)
        self.assertNotIn("Vidange", rappels.texte(self.chef, rappels.composer(self.chef)))

    def test_simulation_et_commande(self):
        self.assertEqual(len(rappels.envoyer(simuler=True)), 2)
        self.assertEqual(mail.outbox, [])
        call_command("envoyer_rappels", verbosity=0, stdout=open("/dev/null", "w"))
        self.assertEqual(len(mail.outbox), 2)

    def test_rien_a_dire_rien_envoye(self):
        Echeance.objects.all().delete()
        PlanEntretien.objects.all().delete()
        ReglageStock.objects.all().delete()
        self.assertEqual(rappels.envoyer(), [])
        self.assertEqual(mail.outbox, [])
