from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "apps.core"
    verbose_name = "Socle"

    def ready(self):
        from django.db.models.signals import post_migrate

        from .roles import creer_roles

        post_migrate.connect(creer_roles, sender=self)
        from .journal import brancher

        brancher()
