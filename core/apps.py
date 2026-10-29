from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # Registers the signals (auto-create profile, delete files with an assignment).
        from . import signals  # noqa: F401
