from django.contrib import admin

from .models import ActionCorrective, Evenement


class ActionInline(admin.TabularInline):
    model = ActionCorrective
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
