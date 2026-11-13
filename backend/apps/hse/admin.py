from django.contrib import admin

from .models import ActionCorrective, DotationEPI, Evenement, Visite


class ActionInline(admin.TabularInline):
    model = ActionCorrective
    fk_name = "evenement"
    exclude = ["visite"]
    extra = 0
    autocomplete_fields = ["responsable"]


@admin.register(Evenement)
class EvenementAdmin(admin.ModelAdmin):
    """Consultation et correction. Le traitement se fait dans l'application."""

    list_display = ["numero", "type", "gravite", "date", "site", "statut"]
    list_filter = ["statut", "type", "gravite", "site"]
    search_fields = ["numero", "description"]
    autocomplete_fields = ["materiel", "declarant"]
    readonly_fields = ["numero", "statut", "clos_le"]
    inlines = [ActionInline]


class ActionDeVisiteInline(ActionInline):
    fk_name = "visite"
    exclude = ["evenement"]


@admin.register(Visite)
class VisiteAdmin(admin.ModelAdmin):
    list_display = ["numero", "date", "site", "lieu", "visiteur", "statut"]
    list_filter = ["statut", "site"]
    search_fields = ["numero", "lieu"]
    autocomplete_fields = ["visiteur"]
    readonly_fields = ["numero", "statut", "clos_le"]
    inlines = [ActionDeVisiteInline]


@admin.register(DotationEPI)
class DotationEPIAdmin(admin.ModelAdmin):
    list_display = ["salarie", "equipement", "precision", "quantite", "date_remise", "a_renouveler_le"]
    list_filter = ["equipement", "salarie__site"]
    search_fields = ["salarie__nom", "salarie__prenoms", "salarie__matricule"]
    autocomplete_fields = ["salarie", "remis_par"]
