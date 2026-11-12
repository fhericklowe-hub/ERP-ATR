from rest_framework import serializers

from .models import Service, Site, Utilisateur


class SiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = ["id", "code", "nom", "ville", "adresse", "est_siege", "actif"]


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ["id", "code", "nom", "actif"]


class UtilisateurSerializer(serializers.ModelSerializer):
    roles = serializers.SlugRelatedField(source="groups", slug_field="name", many=True, read_only=True)
    droits = serializers.SerializerMethodField()

    class Meta:
        model = Utilisateur
        fields = [
            "id", "username", "first_name", "last_name", "email", "telephone", "fonction",
            "site", "service", "roles", "droits", "is_active",
        ]
        read_only_fields = ["username", "is_active"]

    def get_droits(self, obj) -> list[str]:
        return sorted(obj.get_all_permissions())
