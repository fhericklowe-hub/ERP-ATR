from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Service, Site, Utilisateur


class AdminMetier(admin.ModelAdmin):
    """Administration de base : renseigne l'auteur des écritures."""

    def save_model(self, request, obj, form, change):
        if not change:
            obj.cree_par = request.user
        obj.modifie_par = request.user
        super().save_model(request, obj, form, change)


@admin.register(Site)
class SiteAdmin(AdminMetier):
    list_display = ["code", "nom", "ville", "est_siege", "actif"]
    search_fields = ["code", "nom", "ville"]


@admin.register(Service)
class ServiceAdmin(AdminMetier):
    list_display = ["code", "nom", "actif"]
    search_fields = ["code", "nom"]


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    list_display = ["username", "last_name", "first_name", "site", "service", "is_active"]
    list_filter = ["site", "service", "is_active", "groups"]
    fieldsets = UserAdmin.fieldsets + (("Entreprise", {"fields": ("site", "service", "fonction", "telephone")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Entreprise", {"fields": ("site", "service")}),)
