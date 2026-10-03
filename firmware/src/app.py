import asyncio

import machine
import ubinascii
from constants import (
    ALLOWED_ACTUATOR_ACTIONS,
    ALLOWED_SENSOR_ACTIONS,
    TELEMETRY_INTERVAL_SECONDS,
)
from src.actuators.base import BaseActuator, ManualButton
from src.mqtt_manager import MqttManager
from src.network_manager import NetworkManager
from src.sensors.sensor_classes import SENSOR_CLASSES


class GrowHubController:
    def __init__(self, manifest, secrets):
        self.manifest = manifest
        self.secrets = secrets

        # Unique client id per device (prevents MQTT id collisions when
        # several GrowHubs share a broker).
        unique = ubinascii.hexlify(machine.unique_id()).decode()
        self.client_id = f"{manifest['client_id']}-{unique}"

        # Managers
        self.wifi = NetworkManager(
            secrets.get("WIFI_SSID"), secrets.get("WIFI_PASSWORD")
        )
        self.mqtt = MqttManager(
            client_id=self.client_id,
            broker_ip=secrets.get("MQTT_BROKER"),
            user=secrets.get("MQTT_USER"),
            password=secrets.get("MQTT_PASSWORD"),
            port=secrets.get("MQTT_PORT", 1883),
        )

        # Hardware storage
        self.sensors = {}
        self.actuators = {}
        self.buttons = []

        self._setup_hardware()
        self.mqtt.set_callback(self._on_message)

    def _setup_hardware(self):
        # Setup Actuators
        for item in self.manifest["actuators"]:
            self.actuators[item["id"]] = BaseActuator(
                item["pin"], item["id"], item.get("active_low", True)
            )

        # Setup Sensors
        for item in self.manifest["sensors"]:
            cls = SENSOR_CLASSES.get(item["type"])
            if cls:
                # Dynamic unpacking for calibration if it exists
                args = {"pin_number": item["pin"], "sensor_id": item["id"]}
                if "calibration" in item:
                    args.update({"calibration": item["calibration"]})
                self.sensors[item["id"]] = cls(**args)

        # Setup Buttons
        for item in self.manifest["buttons"]:
            btn = ManualButton(item["pin"], item["id"], item["target"])
            self.buttons.append(btn)

    def _on_message(self, topic, msg):
        """Routing logic using getattr for cleaner execution."""
        try:
            parts = topic.decode().split("/")
            if len(parts) < 4:
                return

            category, target_id, action = parts[1], parts[2], msg.decode()

            if category == "actuators":
                target = self.actuators.get(target_id)
                if (
                    target
                    and hasattr(target, action)
                    and action in ALLOWED_ACTUATOR_ACTIONS
                ):
                    getattr(target, action)()
                    # Send feedback
                    self.mqtt.publish(
                        f"{self.client_id}/data/{target_id}/state",
                        {"state": target.human_state()},
                        retain=True,
                    )
            elif category == "sensors" and action in ALLOWED_SENSOR_ACTIONS:
                target = self.sensors.get(target_id)
                if target:
                    result = target.read()
                    if result is not None:
                        # Reuse the telemetry topic/shape so the gateway
                        # logger picks up this on-demand reading.
                        self.mqtt.publish(
                            f"{self.client_id}/telemetry", {target_id: result}
                        )
        except Exception as e:
            print(f"Callback error: {e}")

    async def _read_sensor(self, sensor, retries=3):
        """Read a sensor, retrying asynchronously on None (e.g. DHT timeouts)."""
        for _ in range(retries):
            try:
                value = sensor.read()
            except Exception as e:
                print(f"Sensor read error: {e}")
                value = None
            if value is not None:
                return value
            await asyncio.sleep(2)
        return None

    async def _telemetry_task(self):
        while True:
            if self.wifi.wlan.isconnected() and self.mqtt.is_connected():
                data = {}
                for sid, s in self.sensors.items():
                    data[sid] = await self._read_sensor(s)
                data["actuators"] = {
                    aid: "ON" if act.is_on() else "OFF"
                    for aid, act in self.actuators.items()
                }
                self.mqtt.publish(f"{self.client_id}/telemetry", data)
            await asyncio.sleep(TELEMETRY_INTERVAL_SECONDS)

    async def _listen_task(self):
        while True:
            if self.wifi.wlan.isconnected() and self.mqtt.is_connected():
                self.mqtt.check_msg()
            await asyncio.sleep(0.1)

    async def _button_task(self):
        """Task to check buttons frequently (non-blocking)."""
        while True:
            for btn in self.buttons:
                if btn.is_pressed():
                    target = self.actuators.get(btn.target_id)
                    if target:
                        # 1. Action physique
                        target.toggle()

                        # 2. Feedback MQTT immédiat (pour synchroniser le Dashboard)
                        self.mqtt.publish(
                            f"{self.client_id}/data/{btn.target_id}/state",
                            {"state": target.human_state()},
                            retain=True,
                        )

                        # Debounce: wait until button is released or small delay
                        await asyncio.sleep(0.3)

            # Very short sleep to let other tasks run
            await asyncio.sleep(0.05)

    async def _mqtt_keepalive(self):
        """Reconnect MQTT whenever the link drops (once Wi-Fi is back)."""
        while True:
            if self.wifi.wlan.isconnected() and not self.mqtt.is_connected():
                await self.mqtt.connect()
            await asyncio.sleep(10)

    async def run(self):
        """Entry point for the async loop."""
        await self.wifi.connect()
        if self.wifi.wlan.isconnected():
            await self.mqtt.connect()

        await asyncio.gather(
            self._telemetry_task(),
            self._listen_task(),
            self._button_task(),
            self.wifi.keep_connected(),
            self._mqtt_keepalive(),
        )
