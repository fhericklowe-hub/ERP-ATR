from django.contrib import admin

from apps.core.admin import AdminMetier

from .models import Bien, Contrat, DemandeIntervention, Echeance


@admin.register(Bien)
class BienAdmin(AdminMetier):
    list_display = ["numero", "categorie", "designation", "site", "service", "affecte_a", "etat"]
    list_filter = ["categorie", "etat", "site", "service"]
    search_fields = ["numero", "designation", "marque", "modele", "numero_serie", "immatriculation"]
    autocomplete_fields = ["affecte_a", "fournisseur"]


@admin.register(DemandeIntervention)
class DemandeInterventionAdmin(admin.ModelAdmin):
    """Consultation et correction. Le suivi se fait dans l'application."""

    list_display = ["numero", "cree_le", "objet", "categorie", "priorite", "site", "demandeur", "statut"]
    list_filter = ["statut", "categorie", "priorite", "site"]
    search_fields = ["numero", "objet", "description"]
    readonly_fields = ["numero", "statut", "prise_en_charge_le", "cloturee_le"]
    autocomplete_fields = ["demandeur", "bien", "intervenant", "prestataire"]


@admin.register(Contrat)
class ContratAdmin(AdminMetier):
    list_display = ["numero", "type", "objet", "prestataire", "date_debut", "date_fin", "montant", "statut"]
    list_filter = ["type", "statut", "site"]
    search_fields = ["numero", "objet", "reference", "prestataire__raison_sociale"]
    autocomplete_fields = ["prestataire", "bien"]


@admin.register(Echeance)
class EcheanceAdmin(AdminMetier):
    list_display = ["libelle", "type", "date_echeance", "bien", "contrat", "statut"]
    list_filter = ["type", "statut", "site"]
    search_fields = ["libelle"]
    autocomplete_fields = ["bien", "contrat"]
    readonly_fields = ["statut", "faite_le", "montant_reel"]
