from django.contrib import admin

from .models import Acheteur, DemandeBudget, DevisDemande, LigneBudgetaire, BonCommande, BonReception, LigneBonReception, DemandeAchat, LigneBonCommande, Evenement, LigneDemandeAchat, PieceJointe


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

    list_display = ["numero", "date_demande", "demandeur", "service", "site", "urgence", "statut", "acheteur", "echeance_commande"]
    list_filter = ["statut", "urgence", "service", "site"]
    search_fields = ["numero", "ancien_numero", "numero_or", "equipement_designation"]
    readonly_fields = ["numero", "statut", "acheteur", "recue_le", "echeance_commande", "elements_manquants"]
    inlines = [LigneInline, PieceJointeInline, EvenementInline]


@admin.register(Acheteur)
class AcheteurAdmin(admin.ModelAdmin):
    list_display = ["utilisateur", "disponible"]
    list_editable = ["disponible"]
    autocomplete_fields = ["utilisateur"]


class LigneBonCommandeInline(admin.TabularInline):
    model = LigneBonCommande
    extra = 0


@admin.register(BonCommande)
class BonCommandeAdmin(admin.ModelAdmin):
    """Consultation et correction. Les validations se font dans l'application."""

    list_display = ["numero", "date", "fournisseur", "origine", "service", "acheteur", "statut"]
    list_filter = ["statut", "site", "service", "activite"]
    search_fields = ["numero", "ancien_numero", "objet", "fournisseur__raison_sociale"]
    readonly_fields = ["numero", "statut", "transmis_le"]
    autocomplete_fields = ["fournisseur", "demande", "demande_budget", "acheteur"]
    inlines = [LigneBonCommandeInline]


class LigneBonReceptionInline(admin.TabularInline):
    model = LigneBonReception
    extra = 0


@admin.register(BonReception)
class BonReceptionAdmin(admin.ModelAdmin):
    """Consultation et correction. La validation se fait dans l'application."""

    list_display = ["numero", "date", "commande", "numero_livraison", "receptionnaire", "statut"]
    list_filter = ["statut"]
    search_fields = ["numero", "ancien_numero", "numero_livraison", "commande__numero"]
    readonly_fields = ["numero", "statut", "valide_le", "annule_par", "annule_le", "motif_annulation"]
    autocomplete_fields = ["commande", "receptionnaire"]
    inlines = [LigneBonReceptionInline]


@admin.register(LigneBudgetaire)
class LigneBudgetaireAdmin(admin.ModelAdmin):
    """Budget annuel par service, saisi par le contrôle de gestion."""

    list_display = ["exercice", "service", "intitule", "compte", "montant", "actif"]
    list_filter = ["exercice", "service", "actif"]
    search_fields = ["intitule"]
    autocomplete_fields = ["compte"]


class DevisDemandeInline(admin.TabularInline):
    model = DevisDemande
    extra = 0


@admin.register(DemandeBudget)
class DemandeBudgetAdmin(admin.ModelAdmin):
    """Consultation et correction. Le circuit de validation se fait dans l'application."""

    list_display = ["numero", "type", "date", "demandeur", "service", "intitule", "montant", "statut"]
    list_filter = ["type", "statut", "service", "prevu_budget"]
    search_fields = ["numero", "ancien_numero", "intitule"]
    readonly_fields = ["numero", "statut", "acheteur", "montant"]
    inlines = [DevisDemandeInline]
