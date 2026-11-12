from celery import shared_task


@shared_task
def envoyer_rappels():
    """Lancée chaque matin par le planificateur (voir CELERY_BEAT_SCHEDULE)."""
    from . import rappels

    return len(rappels.envoyer())
