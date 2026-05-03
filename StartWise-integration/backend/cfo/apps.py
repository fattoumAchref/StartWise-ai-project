from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "cfo"

    def ready(self):
        from cfo.session_manager import startup_singletons
        startup_singletons()
