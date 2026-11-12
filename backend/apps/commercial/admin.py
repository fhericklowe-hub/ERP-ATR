from django.contrib import admin

from .models import Devis, LigneDevis, ReglageCommercial


class LigneInline(admin.TabularInline):
    model = LigneDevis
    extra = 0
    autocomplete_fields = ["materiel"]


@admin.register(Devis)
class DevisAdmin(admin.ModelAdmin):
    """Consultation et correction. Le déroulement se fait dans l'application."""

    list_display = ["numero", "date", "client", "libelle", "commercial", "statut"]
    list_filter = ["statut", "site", "activite"]
    search_fields = ["numero", "libelle", "client__raison_sociale"]
    readonly_fields = ["numero", "statut", "reference_client", "accepte_le", "motif"]
    autocomplete_fields = ["client", "commercial"]
    inlines = [LigneInline]


@admin.register(ReglageCommercial)
class ReglageCommercialAdmin(admin.ModelAdmin):
    """Une seule ligne : on l'ouvre pour la modifier, on n'en ajoute pas d'autre."""

    def has_add_permission(self, request):
        return not ReglageCommercial.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
