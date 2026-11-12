from rest_framework import viewsets


class VueMetier(viewsets.ModelViewSet):
    """Vue de base des objets métier : renseigne automatiquement l'auteur des écritures."""

    def perform_create(self, serializer):
        serializer.save(cree_par=self.request.user, modifie_par=self.request.user)

    def perform_update(self, serializer):
        serializer.save(modifie_par=self.request.user)
