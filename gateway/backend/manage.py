#!/usr/bin/env python
"""Django management entry point for the GrowHub gateway."""

import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "growhub.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Django introuvable. Active l'environnement : venv/bin/python"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
