from django.apps import AppConfig
from django.db.models.signals import post_migrate


class MoyensConfig(AppConfig):
    name = "apps.moyens"
    verbose_name = "Moyens généraux"

    def ready(self):
        from .roles import creer_roles

        post_migrate.connect(creer_roles, sender=self)
