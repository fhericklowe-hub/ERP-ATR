from django.contrib import admin

from apps.core.admin import AdminMetier

from .models import Bien, DemandeIntervention


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
