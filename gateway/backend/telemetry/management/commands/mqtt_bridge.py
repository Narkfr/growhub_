"""MQTT ingest worker: subscribes to every device topic and stores the data.

Run as a long-lived process next to the API:

    DJANGO_SETTINGS_MODULE=growhub.settings python -m django mqtt_bridge
    # ou : venv/bin/python gateway/backend/manage.py mqtt_bridge
"""

import logging
import signal
import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections
from growhub import topics
from telemetry import services
from telemetry.mqtt import build_worker_client

logger = logging.getLogger(__name__)

LEAVES = ("telemetry", "state", "status", "info", "ack")
STALE_TRACKER_INTERVAL = 30


class Command(BaseCommand):
    help = "Subscribe to GrowHub MQTT topics and persist telemetry, state and acks."

    def add_arguments(self, parser):
        parser.add_argument(
            "--broker", default=None, help="Adresse du broker (défaut: settings)."
        )
        parser.add_argument("--port", type=int, default=None)
        parser.add_argument(
            "--once",
            action="store_true",
            help="Traiter un message puis quitter (test manuel).",
        )

    def handle(self, *args, **options):
        from django.conf import settings

        broker = options["broker"] or settings.MQTT_BROKER
        port = options["port"] or settings.MQTT_PORT

        client = build_worker_client()
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.connect(broker, port, keepalive=60)

        self._running = True

        def stop(signum, frame):
            self.stdout.write("arrêt demandé, fermeture du worker…")
            self._running = False

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)

        client.loop_start()
        self.stdout.write(self.style.SUCCESS(f"worker MQTT connecté à {broker}:{port}"))
        last_sweep = time.monotonic()
        try:
            while self._running:
                time.sleep(1)
                if options["once"]:
                    self._running = False
                if time.monotonic() - last_sweep >= STALE_TRACKER_INTERVAL:
                    last_sweep = time.monotonic()
                    try:
                        expired = services.expire_pending_commands()
                        if expired:
                            logger.info(
                                "%s commande(s) sans réponse marquée(s) en timeout",
                                expired,
                            )
                    except Exception:
                        logger.exception("échec du balayage des commandes en attente")
        finally:
            client.loop_stop()
            client.disconnect()
            self.stdout.write("worker MQTT arrêté")

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code != 0:
            logger.error("connexion MQTT refusée (rc=%s)", reason_code)
            return
        for leaf in LEAVES:
            client.subscribe(topics.subscription_filter(leaf))
        client.subscribe(f"{topics.ROOT}/provision/+")
        logger.info(
            "abonné aux topics de télémétrie, état, statut, info, ack et provisioning"
        )

    def _on_message(self, client, userdata, message):
        close_old_connections()
        try:
            payload = message.payload
            if not payload:
                return
            kind, result = services.handle_message(message.topic, payload)
            logger.debug("message %s traité (%s)", message.topic, kind)
            return result
        except services.IngestError as exc:
            logger.warning("message ignoré (%s): %s", message.topic, exc)
        except Exception:
            logger.exception("échec du traitement de %s", message.topic)
        finally:
            close_old_connections()
