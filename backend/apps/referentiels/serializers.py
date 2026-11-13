from rest_framework import serializers

from .models import CompteCharge, Projet, Article, Contact, Emplacement, FamilleArticle, Tiers, Unite


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ["id", "tiers", "nom", "fonction", "telephone", "email"]


class SiteClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Emplacement
        fields = ["id", "nom", "adresse", "ville", "actif"]


class TiersSerializer(serializers.ModelSerializer):
    contacts = ContactSerializer(many=True, read_only=True)
    sites = SiteClientSerializer(source="emplacements", many=True, read_only=True)

    class Meta:
        model = Tiers
        fields = [
            "id", "code", "raison_sociale", "est_client", "est_fournisseur", "numero_contribuable",
            "telephone", "email", "adresse", "ville", "actif", "contacts", "sites",
        ]
        extra_kwargs = {"code": {"required": False, "allow_blank": True}}   # vide : numéro automatique

    def validate(self, attrs):
        if self.instance and "code" in attrs and not attrs["code"]:
            raise serializers.ValidationError({"code": "Le code ne peut pas être vidé."})
        return attrs


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
    nature_libelle = serializers.CharField(source="get_nature_display", read_only=True)
    famille_nom = serializers.CharField(source="famille.nom", read_only=True, default="")
    unite_code = serializers.CharField(source="unite.code", read_only=True)

    class Meta:
        model = Article
        fields = ["id", "code", "designation", "nature", "nature_libelle", "famille", "famille_nom", "unite", "unite_code",
                  "gere_en_stock", "actif"]

    def validate_code(self, code):
        code = code.strip()
        autres = Article.objects.filter(code__iexact=code)
        if self.instance:
            autres = autres.exclude(pk=self.instance.pk)
        if autres.exists():   # l'import du stock reconnaît les codes sans tenir compte des majuscules
            raise serializers.ValidationError("Un article porte déjà ce code.")
        return code


class CompteChargeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompteCharge
        fields = ["id", "numero", "libelle", "article_ng", "actif"]


class ProjetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Projet
        fields = ["id", "numero", "nom", "code_analytique", "activite", "type", "actif"]
