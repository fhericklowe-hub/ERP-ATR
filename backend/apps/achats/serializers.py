from django.db import transaction
from rest_framework import serializers

from .models import DemandeAchat, Evenement, LigneDemandeAchat, PieceJointe


class LigneSerializer(serializers.ModelSerializer):
    unite_code = serializers.CharField(source="unite.code", read_only=True)

    class Meta:
        model = LigneDemandeAchat
        fields = ["id", "article", "designation", "reference_constructeur", "quantite", "unite", "unite_code", "observations"]


class PieceJointeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PieceJointe
        fields = ["id", "fichier", "ajoutee_le"]
        read_only_fields = ["ajoutee_le"]


class EvenementSerializer(serializers.ModelSerializer):
    auteur_nom = serializers.CharField(source="auteur.__str__", read_only=True)
    action_libelle = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = Evenement
        fields = ["id", "action", "action_libelle", "statut", "auteur", "auteur_nom", "date", "commentaire"]


class DemandeAchatSerializer(serializers.ModelSerializer):
    lignes = LigneSerializer(many=True)
    pieces_jointes = PieceJointeSerializer(many=True, read_only=True)
    evenements = EvenementSerializer(many=True, read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    demandeur_nom = serializers.CharField(source="demandeur.__str__", read_only=True)
    service_nom = serializers.CharField(source="service.nom", read_only=True)
    site_nom = serializers.CharField(source="site.nom", read_only=True)
    en_retard = serializers.BooleanField(read_only=True)
    modifiable = serializers.BooleanField(read_only=True)
    peut_valider = serializers.SerializerMethodField()

    class Meta:
        model = DemandeAchat
        fields = [
            "id", "numero", "ancien_numero", "statut", "statut_libelle", "date_demande",
            "demandeur", "demandeur_nom", "service", "service_nom", "site", "site_nom", "telephone",
            "numero_or", "date_besoin",
            "piece_technique", "equipement_designation", "equipement_marque", "equipement_modele",
            "equipement_serie", "activite", "activite_autre",
            "urgence", "justification_urgence",
            "recue_le", "echeance_commande", "en_retard", "elements_manquants", "controle_stock",
            "modifiable", "peut_valider", "lignes", "pieces_jointes", "evenements",
        ]
        read_only_fields = ["numero", "statut", "demandeur", "recue_le", "echeance_commande", "elements_manquants"]

    def get_peut_valider(self, obj) -> bool:
        return obj.peut_valider(self.context["request"].user)

    def validate(self, attrs):
        if self.instance and not self.instance.modifiable:
            # Une fois soumise, seul le cadre achats (contrôle de stock, ancien numéro) reste modifiable.
            interdits = set(attrs) - {"controle_stock", "ancien_numero"}
            if interdits:
                raise serializers.ValidationError("Cette demande a été soumise et ne peut plus être modifiée.")
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        lignes = validated_data.pop("lignes", [])
        demande = DemandeAchat.objects.create(**validated_data)
        LigneDemandeAchat.objects.bulk_create(LigneDemandeAchat(demande=demande, **l) for l in lignes)
        return demande

    @transaction.atomic
    def update(self, instance, validated_data):
        lignes = validated_data.pop("lignes", None)
        instance = super().update(instance, validated_data)
        if lignes is not None:
            instance.lignes.all().delete()
            LigneDemandeAchat.objects.bulk_create(LigneDemandeAchat(demande=instance, **l) for l in lignes)
        return instance
