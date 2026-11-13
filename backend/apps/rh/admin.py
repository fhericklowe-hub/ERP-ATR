from django.contrib import admin

from .models import Contrat, PieceSalarie, Salarie


class ContratInline(admin.TabularInline):
    model = Contrat
    extra = 0


class PieceInline(admin.TabularInline):
    model = PieceSalarie
    extra = 0


@admin.register(Salarie)
class SalarieAdmin(admin.ModelAdmin):
    list_display = ["matricule", "nom", "prenoms", "fonction", "site", "service", "statut"]
    list_filter = ["statut", "site", "service", "categorie"]
    search_fields = ["matricule", "nom", "prenoms"]
    autocomplete_fields = ["responsable", "utilisateur"]
    readonly_fields = ["statut", "date_sortie", "motif_sortie"]
    inlines = [ContratInline, PieceInline]
