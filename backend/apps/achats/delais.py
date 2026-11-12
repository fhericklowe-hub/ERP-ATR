"""Délais d'émission du bon de commande selon l'urgence, en temps ouvré.

Horaires de travail : du lundi au vendredi de 8 h à 12 h et de 13 h à 17 h, le samedi de 8 h à 12 h.
Les jours fériés ne sont pas pris en compte.

Les délais en heures comptent toutes les plages travaillées, samedi matin compris. Les délais en jours
comptent les jours du lundi au vendredi : le samedi, demi-journée, n'est pas compté comme un jour.
"""
from datetime import datetime, time, timedelta

MATIN, APRES_MIDI = (time(8), time(12)), (time(13), time(17))
# Plages travaillées par jour de la semaine (0 = lundi).
PLAGES = {**{j: [MATIN, APRES_MIDI] for j in range(5)}, 5: [MATIN], 6: []}


def _plages(jour: datetime):
    """Plages travaillées du jour, sous forme de couples (début, fin) datés."""
    return [(datetime.combine(jour.date(), a, jour.tzinfo), datetime.combine(jour.date(), b, jour.tzinfo))
            for a, b in PLAGES[jour.weekday()]]


def _recaler(d: datetime) -> datetime:
    """Avance jusqu'au prochain instant travaillé."""
    while True:
        for debut, fin in _plages(d):
            if d < debut:
                return debut
            if d < fin:
                return d
        d = datetime.combine(d.date() + timedelta(days=1), time(0), d.tzinfo)


def ajouter_heures_ouvrees(depart: datetime, heures: int) -> datetime:
    d = _recaler(depart)
    reste = timedelta(hours=heures)
    while True:
        fin = next(f for a, f in _plages(d) if a <= d < f)
        if d + reste <= fin:
            return d + reste
        reste -= fin - d
        d = _recaler(fin)


def ajouter_jours_ouvres(depart: datetime, jours: int) -> datetime:
    d = _recaler(depart)
    while jours:
        d += timedelta(days=1)
        if d.weekday() < 5:
            jours -= 1
    return d
