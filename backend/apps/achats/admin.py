from django.contrib import admin

from .models import DemandeAchat, Evenement, LigneDemandeAchat, PieceJointe


class LigneInline(admin.TabularInline):
    model = LigneDemandeAchat
    extra = 0


class PieceJointeInline(admin.TabularInline):
    model = PieceJointe
    extra = 0


class EvenementInline(admin.TabularInline):
    model = Evenement
    extra = 0
    can_delete = False
    readonly_fields = ["action", "statut", "auteur", "date", "commentaire"]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(DemandeAchat)
class DemandeAchatAdmin(admin.ModelAdmin):
    """Consultation et correction. Le circuit de validation se fait dans l'application."""

    list_display = ["numero", "date_demande", "demandeur", "service", "site", "urgence", "statut", "echeance_commande"]
    list_filter = ["statut", "urgence", "service", "site"]
    search_fields = ["numero", "ancien_numero", "numero_or", "equipement_designation"]
    readonly_fields = ["numero", "statut", "recue_le", "echeance_commande", "elements_manquants"]
    inlines = [LigneInline, PieceJointeInline, EvenementInline]
