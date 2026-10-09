"""ASGI entry point (uvicorn/daphne). Needed for the live SSE stream."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "growhub.settings")

application = get_asgi_application()
