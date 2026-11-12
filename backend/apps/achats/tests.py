from datetime import datetime

from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from rest_framework.test import APITestCase

from apps.core.models import Service, Site, Utilisateur
from apps.referentiels.models import Unite

from . import delais
from .models import Acheteur, DemandeAchat


class DelaisTests(SimpleTestCase):
    def test_quatre_heures_dans_la_matinee(self):
        self.assertEqual(delais.ajouter_heures_ouvrees(datetime(2026, 11, 12, 8, 0), 4), datetime(2026, 11, 12, 12, 0))

    def test_la_pause_de_midi_ne_compte_pas(self):
        # jeudi 9 h : 3 h le matin, puis 1 h après la pause
        self.assertEqual(delais.ajouter_heures_ouvrees(datetime(2026, 11, 12, 9, 0), 4), datetime(2026, 11, 12, 14, 0))

    def test_demande_recue_pendant_la_pause(self):
        self.assertEqual(delais.ajouter_heures_ouvrees(datetime(2026, 11, 12, 12, 30), 4), datetime(2026, 11, 12, 17, 0))

    def test_le_samedi_matin_est_travaille(self):
        # vendredi 15 h : 2 h vendredi, puis 2 h samedi matin
        self.assertEqual(delais.ajouter_heures_ouvrees(datetime(2026, 11, 13, 15, 0), 4), datetime(2026, 11, 14, 10, 0))

    def test_samedi_puis_lundi(self):
        # samedi 11 h : 1 h samedi, puis 3 h lundi matin
        self.assertEqual(delais.ajouter_heures_ouvrees(datetime(2026, 11, 14, 11, 0), 4), datetime(2026, 11, 16, 11, 0))

    def test_demande_recue_le_samedi_apres_midi(self):
        self.assertEqual(delais.ajouter_heures_ouvrees(datetime(2026, 11, 14, 15, 0), 4), datetime(2026, 11, 16, 12, 0))

    def test_deux_jours_ouvres_sautent_le_week_end(self):
        self.assertEqual(delais.ajouter_jours_ouvres(datetime(2026, 11, 12, 10, 0), 2), datetime(2026, 11, 16, 10, 0))


class DemandeAchatTests(APITestCase):
    def setUp(self):
        def utilisateur(nom, role):
            u = Utilisateur.objects.create_user(nom, password="x")
            u.groups.add(Group.objects.get(name=role))
            return u

        self.demandeur = utilisateur("mecano", "Achats - Demandeur")
        self.chef = utilisateur("chef", "Achats - Demandeur")
        self.dt = utilisateur("dt", "Achats - Directeur technique")
        self.achats = utilisateur("franck", "Achats - Responsable achats")
        self.autre = utilisateur("autre", "Achats - Demandeur")
        self.service = Service.objects.get(code="TECH")
        self.service.responsable = self.chef
        self.service.save()
        self.site = Site.objects.get(code="SANPEDRO")
        self.unite = Unite.objects.get(code="U")

    def creer(self, **champs):
        self.client.force_authenticate(self.demandeur)
        donnees = {
            "service": self.service.id, "site": self.site.id, "urgence": 2,
            "lignes": [{"designation": "Filtre à huile", "reference_constructeur": "1R-0750", "quantite": "2", "unite": self.unite.id}],
            **champs,
        }
        r = self.client.post("/api/achats/demandes/", donnees, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        return r.data

    def agir(self, utilisateur, id, action, **donnees):
        self.client.force_authenticate(utilisateur)
        return self.client.post(f"/api/achats/demandes/{id}/{action}/", donnees, format="json")

    def test_numerotation(self):
        a, b = self.creer(), self.creer()
        annee = DemandeAchat.objects.first().date_demande.year
        self.assertEqual(a["numero"], f"DA-{annee}-0001")
        self.assertEqual(b["numero"], f"DA-{annee}-0002")
        self.assertEqual(a["demandeur"], self.demandeur.id)

    def test_circuit_normal(self):
        d = self.creer()
        self.assertEqual(self.agir(self.demandeur, d["id"], "soumettre").data["statut"], "ATT_SERVICE")
        r = self.agir(self.chef, d["id"], "valider")
        self.assertEqual(r.data["statut"], "ATT_ACHATS")
        self.assertIsNotNone(r.data["echeance_commande"])
        r = self.agir(self.achats, d["id"], "valider")
        self.assertEqual(r.data["statut"], "VALIDEE")
        self.assertEqual([e["action"] for e in r.data["evenements"]], ["SOUMISSION", "VALIDATION", "ATTRIBUTION", "VALIDATION"])

    def test_circuit_urgent_passe_par_le_directeur_technique(self):
        d = self.creer(urgence=1, justification_urgence="Grue 80T à l'arrêt chez le client")
        self.agir(self.demandeur, d["id"], "soumettre")
        self.assertEqual(self.agir(self.chef, d["id"], "valider").data["statut"], "ATT_DT")
        self.assertEqual(self.agir(self.achats, d["id"], "valider").status_code, 403)
        self.assertEqual(self.agir(self.dt, d["id"], "valider").data["statut"], "ATT_ACHATS")

    def test_urgence_sans_justification_refusee(self):
        d = self.creer(urgence=1)
        r = self.agir(self.demandeur, d["id"], "soumettre")
        self.assertEqual(r.status_code, 400)
        self.assertIn("justification", r.data["detail"][0])

    def test_piece_technique_exige_equipement_et_photo(self):
        d = self.creer(piece_technique=True, equipement_designation="Chariot 5T", equipement_serie="AB-123")
        self.assertEqual(self.agir(self.demandeur, d["id"], "soumettre").status_code, 400)
        photo = SimpleUploadedFile("plaque.jpg", b"image", content_type="image/jpeg")
        r = self.client.post(f"/api/achats/demandes/{d['id']}/pieces-jointes/", {"fichier": photo}, format="multipart")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self.agir(self.demandeur, d["id"], "soumettre").status_code, 200)

    def test_seul_le_valideur_attendu_peut_valider(self):
        d = self.creer()
        self.agir(self.demandeur, d["id"], "soumettre")
        self.assertEqual(self.agir(self.demandeur, d["id"], "valider").status_code, 403)
        self.assertEqual(self.agir(self.achats, d["id"], "valider").status_code, 403)

    def test_refus_exige_un_motif(self):
        d = self.creer()
        self.agir(self.demandeur, d["id"], "soumettre")
        self.assertEqual(self.agir(self.chef, d["id"], "refuser").status_code, 400)
        self.assertEqual(self.agir(self.chef, d["id"], "refuser", commentaire="Déjà en stock").data["statut"], "REFUSEE")

    def test_renvoi_puis_nouvelle_soumission(self):
        d = self.creer()
        self.agir(self.demandeur, d["id"], "soumettre")
        self.agir(self.chef, d["id"], "valider")
        r = self.agir(self.achats, d["id"], "renvoyer", elements_manquants="Référence constructeur illisible")
        self.assertEqual(r.data["statut"], "RENVOYEE")
        self.assertIsNone(r.data["echeance_commande"])
        self.client.force_authenticate(self.demandeur)
        r = self.client.patch(f"/api/achats/demandes/{d['id']}/", {"numero_or": "OR-77"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self.agir(self.demandeur, d["id"], "soumettre").data["statut"], "ATT_SERVICE")

    def test_demande_soumise_non_modifiable_par_le_demandeur(self):
        d = self.creer()
        self.agir(self.demandeur, d["id"], "soumettre")
        r = self.client.patch(f"/api/achats/demandes/{d['id']}/", {"numero_or": "OR-1"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_les_achats_renseignent_le_controle_de_stock(self):
        d = self.creer()
        self.agir(self.demandeur, d["id"], "soumettre")
        self.agir(self.chef, d["id"], "valider")
        self.client.force_authenticate(self.achats)
        r = self.client.patch(f"/api/achats/demandes/{d['id']}/", {"controle_stock": "NON_DISPO"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        r = self.client.patch(f"/api/achats/demandes/{d['id']}/", {"urgence": 3}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_visibilite(self):
        d = self.creer()
        for utilisateur, attendu in [(self.autre, 0), (self.chef, 1), (self.achats, 1), (self.dt, 1)]:
            self.client.force_authenticate(utilisateur)
            self.assertEqual(self.client.get("/api/achats/demandes/").data["count"], attendu, utilisateur)
        self.client.force_authenticate(self.autre)
        self.assertEqual(self.client.get(f"/api/achats/demandes/{d['id']}/").status_code, 404)
        self.assertEqual(self.agir(self.autre, d["id"], "soumettre").status_code, 404)


class AttributionTests(DemandeAchatTests):
    """Attribution des demandes aux acheteurs à leur arrivée aux achats."""

    def setUp(self):
        super().setUp()

        def acheteur(nom):
            u = Utilisateur.objects.create_user(nom, password="x")
            u.groups.add(Group.objects.get(name="Achats - Acheteur"))
            return Acheteur.objects.create(utilisateur=u)

        self.a1, self.a2 = acheteur("acheteur1"), acheteur("acheteur2")

    def envoyer_aux_achats(self):
        d = self.creer()
        self.agir(self.demandeur, d["id"], "soumettre")
        return self.agir(self.chef, d["id"], "valider").data

    def test_repartition_selon_la_charge(self):
        attribuees = [self.envoyer_aux_achats()["acheteur"] for _ in range(4)]
        self.assertEqual(attribuees.count(self.a1.utilisateur_id), 2)
        self.assertEqual(attribuees.count(self.a2.utilisateur_id), 2)

    def test_un_acheteur_indisponible_ne_recoit_rien(self):
        self.a1.disponible = False
        self.a1.save()
        self.assertEqual({self.envoyer_aux_achats()["acheteur"] for _ in range(3)}, {self.a2.utilisateur_id})

    def test_le_moins_charge_recoit_la_demande(self):
        premiere = self.envoyer_aux_achats()
        charge, libre = (self.a1, self.a2) if premiere["acheteur"] == self.a1.utilisateur_id else (self.a2, self.a1)
        self.assertEqual(self.envoyer_aux_achats()["acheteur"], libre.utilisateur_id)
        # la demande du premier acheteur est validée : il redevient le moins chargé
        self.agir(self.achats, premiere["id"], "valider")
        self.assertEqual(self.envoyer_aux_achats()["acheteur"], charge.utilisateur_id)

    def test_sans_acheteur_disponible_la_demande_reste_a_attribuer(self):
        Acheteur.objects.update(disponible=False)
        d = self.envoyer_aux_achats()
        self.assertIsNone(d["acheteur"])
        self.assertEqual(d["evenements"][-1]["commentaire"], "Aucun acheteur disponible")

    def test_le_responsable_achats_reattribue(self):
        d = self.envoyer_aux_achats()
        autre = self.a2 if d["acheteur"] == self.a1.utilisateur_id else self.a1
        self.assertEqual(self.agir(autre.utilisateur, d["id"], "attribuer", acheteur=autre.id).status_code, 403)
        r = self.agir(self.achats, d["id"], "attribuer", acheteur=autre.id)
        self.assertEqual(r.data["acheteur"], autre.utilisateur_id)

    def test_l_acheteur_traite_mais_ne_valide_pas(self):
        d = self.envoyer_aux_achats()
        acheteur = Utilisateur.objects.get(id=d["acheteur"])
        autre = (self.a2 if acheteur == self.a1.utilisateur else self.a1).utilisateur
        self.client.force_authenticate(autre)
        r = self.client.patch(f"/api/achats/demandes/{d['id']}/", {"controle_stock": "DISPO"}, format="json")
        self.assertEqual(r.status_code, 403)
        self.client.force_authenticate(acheteur)
        r = self.client.patch(f"/api/achats/demandes/{d['id']}/", {"controle_stock": "DISPO"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self.agir(acheteur, d["id"], "valider").status_code, 403)
        self.assertEqual(self.agir(acheteur, d["id"], "renvoyer", elements_manquants="Photo floue").data["statut"], "RENVOYEE")

    def test_une_demande_corrigee_revient_au_meme_acheteur(self):
        d = self.envoyer_aux_achats()
        self.agir(self.achats, d["id"], "renvoyer", elements_manquants="Référence")
        self.envoyer_aux_achats()  # entre-temps, l'autre acheteur reçoit une demande
        self.agir(self.demandeur, d["id"], "soumettre")
        self.assertEqual(self.agir(self.chef, d["id"], "valider").data["acheteur"], d["acheteur"])

    def test_charge_de_l_equipe(self):
        self.envoyer_aux_achats()
        self.client.force_authenticate(self.achats)
        r = self.client.get("/api/achats/acheteurs/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(sorted(a["en_cours"] for a in r.data["results"]), [0, 1])
        r = self.client.patch(f"/api/achats/acheteurs/{self.a1.id}/", {"disponible": False}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.client.force_authenticate(self.demandeur)
        self.assertEqual(self.client.get("/api/achats/acheteurs/").status_code, 403)
