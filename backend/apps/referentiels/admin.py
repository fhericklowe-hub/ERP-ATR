from django.contrib import admin

from apps.core.admin import AdminMetier

from .models import Article, CompteCharge, Projet, Contact, Emplacement, FamilleArticle, Tiers, Unite


class ContactInline(admin.TabularInline):
    model = Contact
    extra = 0


@admin.register(Tiers)
class TiersAdmin(AdminMetier):
    list_display = ["code", "raison_sociale", "est_client", "est_fournisseur", "ville", "actif"]
    list_filter = ["est_client", "est_fournisseur", "actif"]
    search_fields = ["code", "raison_sociale"]
    inlines = [ContactInline]


@admin.register(Emplacement)
class EmplacementAdmin(AdminMetier):
    list_display = ["nom", "type", "site", "client", "ville", "actif"]
    list_filter = ["type", "site", "actif"]
    search_fields = ["nom", "ville"]


@admin.register(Article)
class ArticleAdmin(AdminMetier):
    list_display = ["code", "designation", "nature", "famille", "unite", "gere_en_stock", "actif"]
    list_filter = ["nature", "famille", "gere_en_stock", "actif"]
    search_fields = ["code", "designation"]


admin.site.register(Unite)
admin.site.register(FamilleArticle)


@admin.register(CompteCharge)
class CompteChargeAdmin(admin.ModelAdmin):
    list_display = ["numero", "libelle", "article_ng", "actif"]
    search_fields = ["numero", "libelle", "article_ng"]


@admin.register(Projet)
class ProjetAdmin(admin.ModelAdmin):
    list_display = ["numero", "nom", "code_analytique", "activite", "type", "actif"]
    list_filter = ["activite", "type", "actif"]
    search_fields = ["nom", "code_analytique"]
