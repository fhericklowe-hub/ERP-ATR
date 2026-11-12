from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from rest_framework import exceptions, mixins, permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.achats.views import executer_transition
from apps.core.permissions import DroitsModele

from .demandes import DemandeSortie, LigneDemandeSortie
from .models import quantite_en_stock


class LigneDemandeSerializer(serializers.ModelSerializer):
    code = serializers.CharField(source="article.code", read_only=True)
    designation = serializers.CharField(source="article.designation", read_only=True)
    unite = serializers.CharField(source="article.unite.code", read_only=True)
    en_stock = serializers.SerializerMethodField()

    class Meta:
        model = LigneDemandeSortie
        fields = ["id", "article", "code", "designation", "unite", "quantite", "quantite_servie", "en_stock"]
        read_only_fields = ["quantite_servie"]

    def get_en_stock(self, obj):
        """Stock du magasin demandé, montré au magasin tant que la demande est à servir."""
        demande = obj.demande
        if demande.statut != demande.Statut.A_SERVIR or not self.context["request"].user.has_perm("stock.view_mouvement"):
            return None
        return str(quantite_en_stock(obj.article, demande.magasin))


class DemandeSortieSerializer(serializers.ModelSerializer):
    lignes = LigneDemandeSerializer(many=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    demandeur_nom = serializers.CharField(source="demandeur.__str__", read_only=True)
    service_nom = serializers.CharField(source="service.nom", read_only=True)
    magasin_nom = serializers.CharField(source="magasin.nom", read_only=True)
    valide_par_nom = serializers.SerializerMethodField()
    traite_par_nom = serializers.SerializerMethodField()
    bon_sortie_numero = serializers.CharField(source="bon_sortie.numero", read_only=True, default="")
    peut_valider = serializers.SerializerMethodField()
    peut_servir = serializers.SerializerMethodField()
    peut_refuser = serializers.SerializerMethodField()
    peut_annuler = serializers.SerializerMethodField()

    class Meta:
        model = DemandeSortie
        fields = ["id", "numero", "statut", "statut_libelle", "cree_le", "demandeur_nom", "service", "service_nom",
                  "magasin", "magasin_nom", "numero_or", "materiel", "motif", "valide_par_nom", "valide_le",
                  "traite_par_nom", "traite_le", "motif_refus", "bon_sortie", "bon_sortie_numero",
                  "peut_valider", "peut_servir", "peut_refuser", "peut_annuler", "lignes"]
        read_only_fields = ["numero", "statut", "valide_le", "traite_le", "motif_refus", "bon_sortie"]

    def _u(self):
        return self.context["request"].user

    def get_valide_par_nom(self, obj) -> str:
        return str(obj.valide_par) if obj.valide_par_id else ""

    def get_traite_par_nom(self, obj) -> str:
        return str(obj.traite_par) if obj.traite_par_id else ""

    def get_peut_valider(self, obj) -> bool:
        return obj.peut_valider(self._u())

    def get_peut_servir(self, obj) -> bool:
        return obj.peut_servir(self._u())

    def get_peut_refuser(self, obj) -> bool:
        return obj.peut_refuser(self._u())

    def get_peut_annuler(self, obj) -> bool:
        return obj.peut_annuler(self._u())

    def create(self, donnees):
        lignes = [(l["article"], l["quantite"]) for l in donnees.pop("lignes", [])]
        try:
            return DemandeSortie.creer(self._u(), lignes, **donnees)
        except PermissionDenied as e:
            raise exceptions.PermissionDenied(str(e))
        except ValidationError as e:
            raise exceptions.ValidationError({"detail": e.messages})


class DemandeSortieViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """Demandes de sortie. Chacun voit les siennes, un responsable celles de son service, le magasin toutes."""

    serializer_class = DemandeSortieSerializer
    queryset = DemandeSortie.objects.select_related(
        "demandeur", "service", "magasin", "valide_par", "traite_par", "bon_sortie").prefetch_related("lignes__article__unite")
    permission_classes = [DroitsModele]
    filterset_fields = ["statut", "magasin", "service", "demandeur"]
    search_fields = ["numero", "numero_or", "materiel", "motif"]

    def get_queryset(self):
        qs = super().get_queryset()
        u = self.request.user
        if u.has_perm("stock.view_bonsortie"):
            return qs
        return qs.filter(Q(demandeur=u) | Q(service__responsable=u)).distinct()

    transition = dict(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])

    def _transition(self, request, nom, *args):
        executer_transition(self.get_object(), nom, request.user, *args)
        return Response(self.get_serializer(self.get_object()).data)

    @action(**transition)
    def valider(self, request, pk=None):
        return self._transition(request, "valider")

    @action(**transition)
    def refuser(self, request, pk=None):
        return self._transition(request, "refuser", str(request.data.get("commentaire", "")))

    @action(**transition)
    def annuler(self, request, pk=None):
        return self._transition(request, "annuler", str(request.data.get("commentaire", "")))

    @action(**transition)
    def servir(self, request, pk=None):
        quantites = request.data.get("quantites")
        if quantites is not None:
            if not isinstance(quantites, dict):
                raise exceptions.ValidationError({"detail": "Quantités invalides."})
            try:
                quantites = {int(k): serializers.DecimalField(max_digits=12, decimal_places=2).run_validation(v)
                             for k, v in quantites.items()}
            except (ValueError, TypeError):
                raise exceptions.ValidationError({"detail": "Quantités invalides."})
        return self._transition(request, "servir", quantites)
