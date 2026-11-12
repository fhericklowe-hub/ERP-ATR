from rest_framework import serializers

from .models import Article, Contact, Emplacement, FamilleArticle, Tiers, Unite


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ["id", "tiers", "nom", "fonction", "telephone", "email"]


class TiersSerializer(serializers.ModelSerializer):
    contacts = ContactSerializer(many=True, read_only=True)

    class Meta:
        model = Tiers
        fields = [
            "id", "code", "raison_sociale", "est_client", "est_fournisseur", "numero_contribuable",
            "telephone", "email", "adresse", "ville", "actif", "contacts",
        ]


class EmplacementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Emplacement
        fields = ["id", "type", "nom", "site", "client", "adresse", "ville", "actif"]

    def validate(self, attrs):
        instance = Emplacement(**{**({} if not self.instance else {
            "type": self.instance.type, "site": self.instance.site, "client": self.instance.client,
        }), **{k: v for k, v in attrs.items() if k in ("type", "site", "client")}})
        instance.clean()
        return attrs


class UniteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unite
        fields = ["id", "code", "nom"]


class FamilleArticleSerializer(serializers.ModelSerializer):
    class Meta:
        model = FamilleArticle
        fields = ["id", "code", "nom", "parent"]


class ArticleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Article
        fields = ["id", "code", "designation", "nature", "famille", "unite", "gere_en_stock", "actif"]
