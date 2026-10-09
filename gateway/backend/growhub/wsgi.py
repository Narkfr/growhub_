"""WSGI entry point (kept for completeness; deployment uses ASGI)."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "growhub.settings")

application = get_wsgi_application()
