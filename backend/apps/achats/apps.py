from django.apps import AppConfig
from django.db.models.signals import post_migrate


class AchatsConfig(AppConfig):
    name = "apps.achats"
    verbose_name = "Achats"

    def ready(self):
        from .roles import creer_roles

        post_migrate.connect(creer_roles, sender=self)
