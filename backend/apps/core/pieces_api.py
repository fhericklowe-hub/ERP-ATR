from pathlib import Path

from django.contrib.contenttypes.models import ContentType
from django.http import FileResponse
from rest_framework import exceptions, mixins, permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from . import pieces
from .pieces import PieceJointe


class PieceJointeSerializer(serializers.ModelSerializer):
    ajoute_par_nom = serializers.SerializerMethodField()
    supprimable = serializers.SerializerMethodField()

    class Meta:
        model = PieceJointe
        fields = ["id", "nom", "libelle", "taille", "ajoute_par_nom", "ajoute_le", "supprimable"]

    def get_ajoute_par_nom(self, obj) -> str:
        return str(obj.ajoute_par) if obj.ajoute_par_id else ""

    def get_supprimable(self, obj) -> bool:
        u = self.context["request"].user
        return u.is_superuser or obj.ajoute_par_id == u.id


class PieceJointeViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Pièces jointes d'un document : `?modele=achats.demandebudget&objet=12`.

    Les droits sont ceux du document. Les fichiers ne s'ouvrent que par `telecharger`, jamais par une adresse directe."""

    serializer_class = PieceJointeSerializer
    queryset = PieceJointe.objects.select_related("ajoute_par", "content_type")
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    pagination_class = None
    filter_backends = []

    def _document(self, modele, objet_id):
        document = pieces.objet_visible(self.request, str(modele or ""), objet_id)
        if document is None:
            raise exceptions.NotFound("Document introuvable.")
        return document

    def _piece(self):
        """La pièce demandée, si l'utilisateur voit le document auquel elle est attachée."""
        piece = PieceJointe.objects.select_related("content_type", "ajoute_par").filter(pk=self.kwargs["pk"]).first()
        if piece is None:
            raise exceptions.NotFound()
        modele = f"{piece.content_type.app_label}.{piece.content_type.model}"
        self._document(modele, piece.object_id)
        return piece

    def list(self, request, *args, **kwargs):
        document = self._document(request.query_params.get("modele"), request.query_params.get("objet"))
        liste = self.queryset.filter(content_type=ContentType.objects.get_for_model(document), object_id=document.pk)
        return Response({"peut_ajouter": pieces.peut_modifier(request.user, document),
                         "results": self.get_serializer(liste, many=True).data})

    def create(self, request, *args, **kwargs):
        document = self._document(request.data.get("modele"), request.data.get("objet"))
        if not pieces.peut_modifier(request.user, document):
            raise exceptions.PermissionDenied("Vous ne pouvez pas ajouter de pièce à ce document.")
        fichier = request.FILES.get("fichier")
        if not fichier:
            raise exceptions.ValidationError({"fichier": "Choisissez un fichier."})
        if Path(fichier.name).suffix.lower() not in pieces.EXTENSIONS:
            raise exceptions.ValidationError(
                {"fichier": "Type de fichier refusé. Acceptés : PDF, images JPG ou PNG, Word, Excel, e-mail."})
        if fichier.size > pieces.TAILLE_MAX:
            raise exceptions.ValidationError({"fichier": "Fichier trop lourd : 10 Mo au plus."})
        if fichier.size == 0:
            raise exceptions.ValidationError({"fichier": "Ce fichier est vide."})
        piece = PieceJointe.objects.create(
            content_type=ContentType.objects.get_for_model(document), object_id=document.pk, fichier=fichier,
            nom=Path(fichier.name).name[:255], libelle=str(request.data.get("libelle", ""))[:120].strip(),
            taille=fichier.size, ajoute_par=request.user)
        return Response(self.get_serializer(piece).data, status=201)

    def destroy(self, request, *args, **kwargs):
        piece = self._piece()
        if not (request.user.is_superuser or piece.ajoute_par_id == request.user.id):
            raise exceptions.PermissionDenied("Seule la personne qui a ajouté la pièce peut la retirer.")
        piece.fichier.delete(save=False)
        piece.delete()
        return Response(status=204)

    @action(detail=True, methods=["get"])
    def telecharger(self, request, pk=None):
        piece = self._piece()
        type_mime = pieces.AFFICHABLES.get(piece.extension)
        reponse = FileResponse(piece.fichier.open("rb"), as_attachment=type_mime is None, filename=piece.nom,
                               content_type=type_mime or "application/octet-stream")
        reponse["X-Content-Type-Options"] = "nosniff"
        return reponse
