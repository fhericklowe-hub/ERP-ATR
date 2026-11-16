"""Contrôle avant la mise en service : `python manage.py verifier_installation`.

Liste ce qui est prêt, ce qui manque et ce qui mérite attention. Ne modifie rien."""
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from apps.core.models import Service, Site, Societe, Utilisateur


class Command(BaseCommand):
    help = "Vérifie que l'installation est prête pour la mise en service (ne modifie rien)."

    def handle(self, *args, **options):
        self.bloquants = self.attentions = 0
        self.stdout.write("Réglages du serveur")
        self.point(not settings.DEBUG, "DEBUG est désactivé", "DEBUG=True dans .env : à passer à False", bloquant=True)
        self.point(settings.SECRET_KEY not in ("dev-only-change-me", "remplacer-par-une-longue-chaine-aleatoire-de-50-caracteres") and len(settings.SECRET_KEY) >= 40,
                   "SECRET_KEY est personnalisée", "SECRET_KEY n'a pas été remplacée par une longue chaîne aléatoire", bloquant=True)
        moteur = settings.DATABASES["default"]["ENGINE"]
        self.point("postgresql" in moteur, "Base de données PostgreSQL", "La base n'est pas PostgreSQL (SQLite ne convient qu'aux essais)", bloquant=True)
        self.point(bool(settings.EMAIL_HOST), "Envoi des e-mails configuré", "EMAIL_HOST est vide : les rappels par e-mail ne partiront pas")
        self.point(bool(settings.ADRESSE_ERP), "Adresse de l'ERP renseignée", "ADRESSE_ERP est vide : les e-mails ne donneront pas de lien vers l'application")

        self.stdout.write("\nSociété et organisation")
        societe = Societe.objects.first()
        self.point(bool(societe and societe.nom), "Fiche Société renseignée", "Fiche Société absente : les documents PDF n'auront pas d'en-tête", bloquant=True)
        if societe:
            self.point(bool(societe.logo), "Logo chargé", "Logo absent de la fiche Société")
        self.point(Site.objects.filter(actif=True).exists(), f"{Site.objects.filter(actif=True).count()} site(s) actif(s)", "Aucun site actif", bloquant=True)
        sans_responsable = list(Service.objects.filter(actif=True, responsable__isnull=True).values_list("nom", flat=True))
        self.point(not sans_responsable, "Chaque service actif a un responsable",
                   "Services sans responsable (leurs demandes ne pourront pas être validées) : " + ", ".join(sans_responsable))

        self.stdout.write("\nComptes et rôles")
        actifs = Utilisateur.objects.filter(is_active=True)
        self.point(actifs.filter(is_superuser=True).exists(), "Un administrateur existe", "Aucun administrateur : lancer createsuperuser", bloquant=True)
        demo = [u.username for u in actifs.filter(username__in=["responsable", "controleur", "acheteur", "magasinier", "chef", "mecanicien", "commercial"]) if u.check_password("demo-atr")]
        self.point(not demo, "Pas de compte de démonstration avec son mot de passe connu",
                   "Comptes de démonstration encore ouverts avec le mot de passe de la démonstration : " + ", ".join(demo), bloquant=True)
        sans_role = actifs.filter(is_superuser=False, groups__isnull=True).count()
        self.point(sans_role == 0, "Tous les comptes actifs ont un rôle", f"{sans_role} compte(s) actif(s) sans aucun rôle")
        vides = list(Group.objects.filter(user__isnull=True).order_by("name").values_list("name", flat=True))
        self.point(not vides, "Chaque rôle est attribué à quelqu'un", f"{len(vides)} rôle(s) attribué(s) à personne : " + ", ".join(vides))
        sans_signature = [u.username for u in actifs.filter(groups__name__in=["Achats - Responsable achats", "Achats - Contrôleur de gestion"]).distinct() if not u.signature]
        self.point(not sans_signature, "Signatures des valideurs de bons de commande chargées",
                   "Signature absente pour : " + ", ".join(sans_signature) + " (le bon de commande sortira sans leur signature)")

        self.stdout.write("\nDonnées de départ")
        from apps.referentiels.models import Article, Tiers
        from apps.rh.models import Salarie
        from apps.technique.models import Materiel
        for libelle, nombre in [("fournisseur(s)", Tiers.objects.filter(est_fournisseur=True).count()), ("client(s)", Tiers.objects.filter(est_client=True).count()),
                                ("article(s)", Article.objects.count()), ("matériel(s) au parc", Materiel.objects.count()), ("salarié(s)", Salarie.objects.count())]:
            self.point(nombre > 0, f"{nombre} {libelle}", f"Aucun {libelle.replace('(s)', '')} : import à faire depuis l'écran correspondant")

        self.stdout.write("")
        if self.bloquants:
            self.stdout.write(self.style.ERROR(f"{self.bloquants} point(s) bloquant(s), {self.attentions} point(s) d'attention. À corriger avant la mise en service."))
        elif self.attentions:
            self.stdout.write(self.style.WARNING(f"Aucun point bloquant, {self.attentions} point(s) d'attention."))
        else:
            self.stdout.write(self.style.SUCCESS("Tout est prêt pour la mise en service."))

    def point(self, ok, si_oui, si_non, bloquant=False):
        if ok:
            self.stdout.write(f"  [OK]        {si_oui}")
        elif bloquant:
            self.bloquants += 1
            self.stdout.write(self.style.ERROR(f"  [BLOQUANT]  {si_non}"))
        else:
            self.attentions += 1
            self.stdout.write(self.style.WARNING(f"  [ATTENTION] {si_non}"))
