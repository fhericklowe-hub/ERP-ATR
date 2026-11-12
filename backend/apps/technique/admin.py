from django.contrib import admin

from apps.core.admin import AdminMetier

from .models import Materiel, OrdreReparation


@admin.register(Materiel)
class MaterielAdmin(AdminMetier):
    list_display = ["code", "type", "designation", "immatriculation", "site", "etat"]
    list_filter = ["type", "etat", "site", "activite"]
    search_fields = ["code", "designation", "marque", "modele", "numero_serie", "immatriculation"]
    autocomplete_fields = ["emplacement"]


@admin.register(OrdreReparation)
class OrdreReparationAdmin(admin.ModelAdmin):
    """Consultation et correction. Le déroulement se fait dans l'application."""

    list_display = ["numero", "cree_le", "materiel", "type", "mecanicien", "statut"]
    list_filter = ["statut", "type"]
    search_fields = ["numero", "description", "materiel__code"]
    readonly_fields = ["numero", "statut", "demarre_le", "termine_le", "cloture_le"]
    autocomplete_fields = ["materiel", "demandeur", "mecanicien"]
