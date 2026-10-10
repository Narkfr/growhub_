"""Le worker d'ingestion vit plus longtemps que sa connexion à la base.

Quand la base redémarre (recréation de conteneur, redémarrage du service), la
connexion détenue par le worker est morte sans qu'il le sache : tout accès lève
alors « the connection is closed ». Constaté en production : un traceback toutes
les 30 s dans le balayage des commandes, jusqu'au redémarrage du worker.
"""

import pytest
from django.db import OperationalError
from telemetry import services
from telemetry.management.commands.mqtt_bridge import Command

pytestmark = pytest.mark.django_db


def test_the_sweep_reopens_a_stale_connection(monkeypatch):
    """Le balayage remet la connexion à zéro avant de toucher la base."""
    calls = []
    monkeypatch.setattr(
        "telemetry.management.commands.mqtt_bridge.close_old_connections",
        lambda: calls.append("close"),
    )
    monkeypatch.setattr(
        services, "expire_pending_commands", lambda: calls.append("expire") or 0
    )

    Command().sweep()

    assert calls == ["close", "expire"]


def test_a_failing_sweep_is_logged_not_propagated(monkeypatch):
    """Un échec de balayage ne doit pas emporter le worker."""

    def boom():
        raise OperationalError("the connection is closed")

    monkeypatch.setattr(services, "expire_pending_commands", boom)

    assert Command().sweep() == 0
