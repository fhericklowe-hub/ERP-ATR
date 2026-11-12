from django.contrib import admin

from .models import BonSortie, DemandeSortie, Mouvement, ReglageStock


class LectureSeule(admin.ModelAdmin):
    """Le stock ne se corrige pas dans l'administration : passer par un ajustement ou une annulation."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Mouvement)
class MouvementAdmin(LectureSeule):
    list_display = ["date", "type", "article", "magasin", "quantite", "motif", "auteur"]
    list_filter = ["type", "magasin"]
    search_fields = ["article__code", "article__designation", "motif"]


@admin.register(BonSortie)
class BonSortieAdmin(LectureSeule):
    list_display = ["numero", "date", "magasin", "numero_or", "materiel", "remis_a", "statut"]
    list_filter = ["statut", "magasin"]
    search_fields = ["numero", "numero_or", "materiel"]


@admin.register(ReglageStock)
class ReglageStockAdmin(admin.ModelAdmin):
    list_display = ["article", "magasin", "seuil_mini", "casier"]
    list_filter = ["magasin"]
    autocomplete_fields = ["article", "magasin"]


@admin.register(DemandeSortie)
class DemandeSortieAdmin(LectureSeule):
    list_display = ["numero", "cree_le", "demandeur", "service", "magasin", "numero_or", "statut"]
    list_filter = ["statut", "magasin", "service"]
    search_fields = ["numero", "numero_or", "materiel"]
