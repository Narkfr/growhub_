"""Background MQTT subscriber that feeds the device registry.

Mirrors the topic layout already used by ``telemetry_logger.py``:

- ``+/telemetry``          full sensor + actuator snapshot (JSON)
- ``+/data/+/state``       single actuator state change (JSON)
- ``+/status``             device online/offline (plain string, retained)
"""

import json
import logging
import time

import paho.mqtt.client as mqtt

log = logging.getLogger(__name__)

TELEMETRY_TOPIC = "+/telemetry"
ACTUATOR_TOPIC = "+/data/+/state"
STATUS_TOPIC = "+/status"


def handle_message(registry, topic, payload_bytes):
    """Route one MQTT message into the registry.

    Returns ``True`` when the registry changed (the message was actionable).
    Malformed JSON is dropped rather than crashing the bridge.
    """
    parts = topic.split("/")
    if len(parts) < 2:
        return False
    client_id = parts[0]
    category = parts[1]

    if category == "status":
        registry.apply_status(client_id, payload_bytes)
        return True

    try:
        payload = json.loads(payload_bytes.decode())
    except (ValueError, UnicodeDecodeError):
        log.warning("Dropping non-JSON message on %s", topic)
        return False

    if category == "telemetry" and isinstance(payload, dict):
        registry.apply_telemetry(client_id, payload)
        return True

    if category == "data" and len(parts) >= 4 and parts[3] == "state":
        registry.apply_actuator_event(client_id, parts[2], payload)
        return True

    return False


class MqttBridge:
    """Connects to the broker and streams messages into a registry."""

    def __init__(
        self,
        registry,
        broker,
        port,
        username=None,
        password=None,
        on_update=None,
    ):
        self.registry = registry
        self.broker = broker
        self.port = int(port)
        self.username = username
        self.password = password
        self.on_update = on_update

    def _make_client(self):
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "GrowHubAPI")
        if self.username:
            client.username_pw_set(self.username, self.password)
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        return client

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            client.subscribe(TELEMETRY_TOPIC)
            client.subscribe(ACTUATOR_TOPIC)
            client.subscribe(STATUS_TOPIC)
            log.info("Connected to MQTT broker; subscribed to live topics")

    def _on_message(self, client, userdata, msg):
        changed = handle_message(self.registry, msg.topic, msg.payload)
        if changed and self.on_update is not None:
            self.on_update()

    def start(self):
        """Block forever, retrying the connection if the broker is down."""
        while True:
            client = self._make_client()
            try:
                client.connect(self.broker, self.port, keepalive=60)
                client.loop_forever()
            except Exception as exc:  # noqa: BLE001 - resilient service loop
                log.warning("MQTT connection failed (%s); retrying in 5s", exc)
                time.sleep(5)
