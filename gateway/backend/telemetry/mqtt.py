"""Thin paho-mqtt wrapper: one lazy publisher for the API, one client for the worker."""

import json
import logging
import os
import socket
import threading

from django.conf import settings

logger = logging.getLogger(__name__)


def process_client_id(base):
    """Identifiant client unique par processus (et par conteneur).

    Un identifiant MQTT ne porte qu'une seule session : deux processus qui
    publient sous le même nom se déconnectent mutuellement en boucle — le broker
    journalise ``session taken over`` sans fin, et l'API comme le worker
    publient des identifiants d'appairage.

    Le PID ne suffit pas : dans deux conteneurs différents, le processus
    principal vaut 1 de part et d'autre. Le nom d'hôte du conteneur complète donc
    le suffixe.
    """
    host = socket.gethostname().split(".")[0][:8]
    return f"{base}-{host}-{os.getpid():x}"


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
        self.client_id = process_client_id(client_id or "gh-api")
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


_SHARED: dict[str, MqttPublisher] = {}


def shared_publisher(base):
    """Le publicateur du processus, un par usage — jamais un par requête.

    Un `MqttPublisher` ouvre une session MQTT et la garde ouverte (`loop_start`
    le fait se reconnecter tout seul). Comme tous ceux d'un même processus
    portent le même identifiant client, en créer un par requête HTTP fait que
    chacun déloge le précédent, qui se reconnecte et redéloge le suivant : une
    tempête de connexions. Constaté en production — des centaines par minute —
    jusqu'à faire trébucher la liaison du boîtier, qui publiait alors des paquets
    que le broker rejetait (`malformed packet`).
    """
    if base not in _SHARED:
        _SHARED[base] = MqttPublisher(client_id=base)
    return _SHARED[base]
