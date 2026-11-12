from django.contrib import admin

from apps.core.admin import AdminMetier

from .models import Materiel, OrdreReparation, PlanEntretien, ReglageAtelier, TempsPasse


@admin.register(Materiel)
class MaterielAdmin(AdminMetier):
    list_display = ["code", "type", "designation", "immatriculation", "site", "etat"]
    list_filter = ["type", "etat", "site", "activite"]
    search_fields = ["code", "designation", "marque", "modele", "numero_serie", "immatriculation"]
    autocomplete_fields = ["emplacement"]


class TempsInline(admin.TabularInline):
    model = TempsPasse
    extra = 0
    autocomplete_fields = ["mecanicien"]
    readonly_fields = ["taux_horaire"]


@admin.register(ReglageAtelier)
class ReglageAtelierAdmin(admin.ModelAdmin):
    """Une seule ligne : on l'ouvre pour la modifier, on n'en ajoute pas d'autre."""

    def has_add_permission(self, request):
        return not ReglageAtelier.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OrdreReparation)
class OrdreReparationAdmin(admin.ModelAdmin):
    """Consultation et correction. Le déroulement se fait dans l'application."""

    list_display = ["numero", "cree_le", "materiel", "type", "mecanicien", "statut"]
    list_filter = ["statut", "type"]
    search_fields = ["numero", "description", "materiel__code"]
    readonly_fields = ["numero", "statut", "demarre_le", "termine_le", "cloture_le"]
    autocomplete_fields = ["materiel", "demandeur", "mecanicien"]
    inlines = [TempsInline]


@admin.register(PlanEntretien)
class PlanEntretienAdmin(AdminMetier):
    list_display = ["materiel", "intitule", "intervalle_heures", "intervalle_km", "intervalle_mois", "dernier_le", "actif"]
    list_filter = ["actif"]
    search_fields = ["intitule", "materiel__code", "materiel__designation"]
    autocomplete_fields = ["materiel"]
