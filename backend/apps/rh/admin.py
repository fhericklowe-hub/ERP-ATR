from django.contrib import admin

from .conges import DemandeAbsence, ReglageRH
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


@admin.register(ReglageRH)
class ReglageRHAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not ReglageRH.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DemandeAbsence)
class DemandeAbsenceAdmin(admin.ModelAdmin):
    """Consultation. Le circuit se fait dans l'application."""

    list_display = ["numero", "salarie", "type", "date_debut", "date_fin", "jours", "statut"]
    list_filter = ["statut", "type"]
    search_fields = ["numero", "salarie__nom", "salarie__matricule"]
    autocomplete_fields = ["salarie"]
    readonly_fields = ["numero", "statut", "jours"]
