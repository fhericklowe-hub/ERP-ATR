"""Listes communes à la demande d'achat et au bon de commande."""
from django.db import models


class Activite(models.TextChoices):
    MANUTENTION = "MANUTENTION", "Manutention"
    LEVAGE = "LEVAGE", "Levage"
    TRANSPORT = "TRANSPORT", "Transport"
    AUTRE = "AUTRE", "Autre"
