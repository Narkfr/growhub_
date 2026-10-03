"""Run the GrowHub live API: MQTT bridge + Flask server.

Usage: ``python -m gateway.api`` (from the repo root, with the gateway
dependencies installed in the active environment).
"""

import os
import threading

from dotenv import load_dotenv

from .app import create_app
from .mqtt_bridge import MqttBridge
from .registry import DeviceRegistry, EventHub
from .state import state_payload

load_dotenv()

HOST = os.getenv("GROWHUB_API_HOST", "0.0.0.0")
PORT = int(os.getenv("GROWHUB_API_PORT", "5001"))
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")


def main():
    registry = DeviceRegistry()
    hub = EventHub()

    def on_update():
        hub.publish(state_payload(registry))

    bridge = MqttBridge(
        registry,
        broker=MQTT_BROKER,
        port=MQTT_PORT,
        username=MQTT_USER,
        password=MQTT_PASSWORD,
        on_update=on_update,
    )
    threading.Thread(target=bridge.start, name="mqtt-bridge", daemon=True).start()

    app = create_app(registry=registry, hub=hub)
    app.run(host=HOST, port=PORT, threaded=True)


if __name__ == "__main__":
    main()
