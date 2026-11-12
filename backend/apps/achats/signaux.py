"""Signaux émis par les achats, pour que les autres modules (le stock) réagissent sans que les achats les connaissent.
Ils sont envoyés dans la transaction de l'opération : une erreur levée par un récepteur annule l'opération."""
from django.dispatch import Signal

reception_validee = Signal()   # sender=BonReception, bon, utilisateur
reception_annulee = Signal()   # sender=BonReception, bon, utilisateur (la réception était validée)
