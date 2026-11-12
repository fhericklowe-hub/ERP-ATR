"""Délais d'émission du bon de commande selon l'urgence, en temps ouvré.

Hypothèse : jours ouvrés du lundi au vendredi, de 8 h à 17 h. Les jours fériés ne sont pas pris en compte.
"""
from datetime import datetime, time, timedelta

DEBUT, FIN = time(8, 0), time(17, 0)


def _ouvre(d: datetime) -> bool:
    return d.weekday() < 5


def _recaler(d: datetime) -> datetime:
    """Avance jusqu'au prochain instant ouvré."""
    if _ouvre(d) and d.time() < DEBUT:
        return d.replace(hour=DEBUT.hour, minute=0, second=0, microsecond=0)
    while not _ouvre(d) or d.time() >= FIN:
        d = (d + timedelta(days=1)).replace(hour=DEBUT.hour, minute=0, second=0, microsecond=0)
    return d


def ajouter_heures_ouvrees(depart: datetime, heures: int) -> datetime:
    d = _recaler(depart)
    reste = timedelta(hours=heures)
    while True:
        fin_journee = d.replace(hour=FIN.hour, minute=0, second=0, microsecond=0)
        if d + reste <= fin_journee:
            return d + reste
        reste -= fin_journee - d
        d = _recaler(fin_journee)


def ajouter_jours_ouvres(depart: datetime, jours: int) -> datetime:
    d = _recaler(depart)
    while jours:
        d += timedelta(days=1)
        if _ouvre(d):
            jours -= 1
    return d
