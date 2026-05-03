from django.apps import AppConfig


class ApiConfig(AppConfig):
    name = "legal_advisor"

    def ready(self):
        # Import here so Django is fully set up before we touch global state.
        # This runs once at server startup (not on every request).
        from . import state  # noqa: F401  initialises chroma + embeddings
