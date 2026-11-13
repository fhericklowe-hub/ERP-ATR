from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from rest_framework import exceptions, mixins, parsers, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.export import ExportExcel
from apps.core.permissions import DroitsModele

from .models import Acheteur, DemandeAchat, PieceJointe
from .serializers import AcheteurSerializer, DemandeAchatSerializer, PieceJointeSerializer


def executer_transition(objet, nom, utilisateur, *args):
    """Joue une étape du circuit et traduit ses refus en erreurs d'API."""
    try:
        return getattr(objet, nom)(utilisateur, *args)
    except DjangoPermissionDenied as e:
        raise exceptions.PermissionDenied(str(e))
    except DjangoValidationError as e:
        raise exceptions.ValidationError({"detail": e.messages})


class AcheteurViewSet(mixins.ListModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Équipe achats : charge en cours et disponibilité de chaque acheteur."""

    serializer_class = AcheteurSerializer
    permission_classes = [DroitsModele]
    queryset = Acheteur.objects.none()  # sert au contrôle des droits ; la liste réelle vient de get_queryset

    def get_queryset(self):
        return Acheteur.avec_charge()


class DemandeAchatViewSet(ExportExcel, mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                          mixins.ListModelMixin, viewsets.GenericViewSet):
    """Demandes d'achat. Pas de suppression : une demande reste dans l'historique."""

    export_titre, export_fichier = "Demandes d'achat", "demandes-achat"
    export_colonnes = [
        ("N°", "numero"), ("Ancien n°", "ancien_numero"), ("Date", "date_demande", "date"), ("Statut", "statut_libelle"),
        ("Demandeur", "demandeur_nom"), ("Service", "service_nom"), ("Site", "site_nom"), ("N° OR", "numero_or"),
        ("Équipement", "equipement_designation"), ("Urgence", "urgence"), ("Date de besoin", "date_besoin", "date"),
        ("Acheteur", "acheteur_nom"), ("Échéance de commande", "echeance_commande", "date"), ("En retard", "en_retard", "oui_non"),
    ]
    serializer_class = DemandeAchatSerializer
    queryset = DemandeAchat.objects.select_related("demandeur", "service", "site", "acheteur").prefetch_related(
        "lignes__unite", "pieces_jointes", "evenements__auteur"
    )
    filterset_fields = ["statut", "urgence", "service", "site", "demandeur", "acheteur"]
    search_fields = ["numero", "ancien_numero", "numero_or", "equipement_designation", "lignes__designation"]
    ordering_fields = ["cree_le", "date_besoin", "urgence", "echeance_commande"]

    def get_queryset(self):
        qs = super().get_queryset()
        u = self.request.user
        if u.has_perm("achats.voir_toutes_demandeachat"):
            return qs
        # Chacun voit ses demandes ; un responsable voit aussi celles de son service.
        return qs.filter(Q(demandeur=u) | Q(service__responsable=u)).distinct()

    def perform_create(self, serializer):
        u = self.request.user
        serializer.save(demandeur=u, cree_par=u, modifie_par=u)

    def update(self, request, *args, **kwargs):
        demande, u = self.get_object(), request.user
        if demande.modifiable and demande.demandeur_id != u.id:
            raise exceptions.PermissionDenied("Seul le demandeur peut modifier sa demande.")
        if not demande.modifiable and not demande.peut_traiter(u):
            raise exceptions.PermissionDenied("Cette demande a été soumise et ne peut plus être modifiée.")
        return super().update(request, *args, **kwargs)

    def perform_update(self, serializer):
        serializer.save(modifie_par=self.request.user)

    def _transition(self, request, nom, *args):
        executer_transition(self.get_object(), nom, request.user, *args)
        return Response(self.get_serializer(self.get_object()).data)

    # Les transitions exigent d'être connecté ; le droit précis est vérifié par le circuit lui-même.
    transition = dict(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])

    @action(**transition)
    def soumettre(self, request, pk=None):
        return self._transition(request, "soumettre")

    @action(**transition)
    def valider(self, request, pk=None):
        return self._transition(request, "valider", request.data.get("commentaire", ""))

    @action(**transition)
    def refuser(self, request, pk=None):
        return self._transition(request, "refuser", request.data.get("commentaire", ""))

    @action(**transition)
    def renvoyer(self, request, pk=None):
        return self._transition(request, "renvoyer", request.data.get("elements_manquants", ""))

    @action(**transition)
    def attribuer(self, request, pk=None):
        acheteur = Acheteur.objects.select_related("utilisateur").filter(id=request.data.get("acheteur")).first()
        if not acheteur:
            raise exceptions.ValidationError({"detail": ["Choisissez un acheteur."]})
        return self._transition(request, "attribuer", acheteur)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated],
            parser_classes=[parsers.MultiPartParser], url_path="pieces-jointes")
    def pieces_jointes(self, request, pk=None):
        demande = self.get_object()
        if not demande.modifiable or demande.demandeur_id != request.user.id:
            raise exceptions.PermissionDenied("Seul le demandeur peut joindre un fichier, avant la soumission.")
        s = PieceJointeSerializer(data=request.data, context=self.get_serializer_context())
        s.is_valid(raise_exception=True)
        s.save(demande=demande, ajoutee_par=request.user)
        return Response(s.data, status=201)

    @action(detail=True, methods=["delete"], permission_classes=[permissions.IsAuthenticated],
            url_path=r"pieces-jointes/(?P<piece_id>\d+)")
    def supprimer_piece_jointe(self, request, pk=None, piece_id=None):
        demande = self.get_object()
        if not demande.modifiable or demande.demandeur_id != request.user.id:
            raise exceptions.PermissionDenied("Seul le demandeur peut retirer un fichier, avant la soumission.")
        PieceJointe.objects.filter(demande=demande, id=piece_id).delete()
        return Response(status=204)
