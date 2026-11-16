from django.contrib import admin

from .models import OrdreTransport


@admin.register(OrdreTransport)
class OrdreTransportAdmin(admin.ModelAdmin):
    """Consultation et correction. Le déroulement se fait dans l'application."""

    list_display = ["numero", "client", "origine", "destination", "date_prevue", "tracteur", "chauffeur", "statut"]
    list_filter = ["statut", "site"]
    search_fields = ["numero", "client__raison_sociale", "reference_client", "chauffeur", "tracteur__code"]
    autocomplete_fields = ["client", "tracteur", "remorque"]
    readonly_fields = ["numero", "statut", "depart_le", "arrivee_le"]
