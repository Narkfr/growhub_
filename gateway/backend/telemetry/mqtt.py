"""Thin paho-mqtt wrapper: one lazy publisher for the API, one client for the worker."""

import json
import logging
import threading

from django.conf import settings

logger = logging.getLogger(__name__)


class MqttPublisher:
    """Lazily connected client used to push commands to devices.

    Connections are reused across requests and re-established automatically by
    paho when they drop; ``publish`` raises if the broker is unreachable so the
    caller can audit the failure instead of pretending the command went out.
    """

    def __init__(
        self, broker=None, port=None, username=None, password=None, client_id=None
    ):
        self.broker = broker or settings.MQTT_BROKER
        self.port = int(port or settings.MQTT_PORT)
        self.username = username or settings.MQTT_USER
        self.password = password if password is not None else settings.MQTT_PASSWORD
        self.client_id = client_id or "growhub-backend"
        self._client = None
        self._lock = threading.Lock()

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        import paho.mqtt.client as mqtt

        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=self.client_id,
            protocol=mqtt.MQTTv311,
        )
        if self.username:
            client.username_pw_set(self.username, self.password)
        client.connect(self.broker, self.port, keepalive=30)
        client.loop_start()
        self._client = client
        return client

    def publish(self, topic, payload, retain=False, qos=0):
        body = payload if isinstance(payload, str) else json.dumps(payload, default=str)
        with self._lock:
            client = self._ensure_client()
            info = client.publish(topic, body, qos=qos, retain=retain)
            if info.rc != 0:
                raise OSError(f"publication MQTT refusée sur {topic} (rc={info.rc})")
            return info

    def close(self):
        with self._lock:
            if self._client is not None:
                self._client.loop_stop()
                self._client.disconnect()
                self._client = None


def build_worker_client(client_id="growhub-worker"):
    """Client for the ingest loop: subscribes to every device topic."""
    import paho.mqtt.client as mqtt

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2, client_id=client_id, protocol=mqtt.MQTTv311
    )
    if settings.MQTT_USER:
        client.username_pw_set(settings.MQTT_USER, settings.MQTT_PASSWORD)
    return client
