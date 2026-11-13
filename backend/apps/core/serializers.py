from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as ErreurDjango
from rest_framework import serializers

from .models import Service, Site, Utilisateur


class SiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = ["id", "code", "nom", "ville", "adresse", "est_siege", "actif"]


class ServiceSerializer(serializers.ModelSerializer):
    responsable_nom = serializers.SerializerMethodField()

    class Meta:
        model = Service
        fields = ["id", "code", "nom", "responsable", "responsable_nom", "actif"]

    def get_responsable_nom(self, service) -> str:
        return str(service.responsable) if service.responsable_id else ""

    def validate_responsable(self, personne):
        if personne and not personne.is_active:
            raise serializers.ValidationError("Ce compte est désactivé : il ne peut pas valider les demandes du service.")
        return personne


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


class CompteSerializer(serializers.ModelSerializer):
    """Le compte vu par celui qui gère les comptes : identité, rôles, mot de passe (jamais relu)."""

    roles = serializers.SlugRelatedField(source="groups", slug_field="name", many=True, queryset=Group.objects.all(), required=False)
    mot_de_passe = serializers.CharField(write_only=True, required=False, allow_blank=True, trim_whitespace=False)
    site_nom = serializers.CharField(source="site.nom", read_only=True, default="")
    service_nom = serializers.CharField(source="service.nom", read_only=True, default="")
    administrateur = serializers.SerializerMethodField()
    derniere_connexion = serializers.DateTimeField(source="last_login", read_only=True)

    class Meta:
        model = Utilisateur
        fields = ["id", "username", "first_name", "last_name", "email", "telephone", "fonction", "site", "site_nom",
                  "service", "service_nom", "roles", "is_active", "mot_de_passe", "administrateur", "derniere_connexion"]

    def get_administrateur(self, compte) -> bool:
        return compte.is_superuser or compte.is_staff

    def validate_username(self, identifiant):
        if self.instance and identifiant != self.instance.username:
            raise serializers.ValidationError("L'identifiant ne se change pas.")
        return identifiant

    def validate(self, attrs):
        demandeur = self.context["request"].user
        moi = self.instance is not None and self.instance.pk == demandeur.pk
        if self.instance and (self.instance.is_superuser or self.instance.is_staff) and not demandeur.is_superuser:
            raise serializers.ValidationError("Le compte d'un administrateur ne se modifie que par un administrateur.")
        if moi and "groups" in attrs and {g.pk for g in attrs["groups"]} != set(self.instance.groups.values_list("pk", flat=True)):
            raise serializers.ValidationError({"roles": "On ne change pas ses propres rôles."})
        if moi and attrs.get("is_active") is False:
            raise serializers.ValidationError({"is_active": "On ne désactive pas son propre compte."})
        mot = attrs.get("mot_de_passe") or ""
        if not self.instance and not mot:
            raise serializers.ValidationError({"mot_de_passe": "Donnez un mot de passe de départ."})
        if mot:
            candidat = self.instance or Utilisateur(**{k: v for k, v in attrs.items() if k in ("username", "first_name", "last_name", "email")})
            try:
                validate_password(mot, candidat)
            except ErreurDjango as e:
                raise serializers.ValidationError({"mot_de_passe": list(e.messages)})
        return attrs

    def _enregistrer(self, compte, donnees):
        mot = donnees.pop("mot_de_passe", "")
        roles = donnees.pop("groups", None)
        for champ, valeur in donnees.items():
            setattr(compte, champ, valeur)
        if mot:
            compte.set_password(mot)
        compte.save()
        if roles is not None:
            compte.groups.set(roles)
        return compte

    def create(self, donnees):
        return self._enregistrer(Utilisateur(), donnees)

    def update(self, compte, donnees):
        return self._enregistrer(compte, donnees)
