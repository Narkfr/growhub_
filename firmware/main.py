import asyncio
import json

try:
    from secrets import secrets
except ImportError:
    print("Error: secrets.py is missing!")
    secrets = {}

from constants import ALLOWED_ACTUATOR_ACTIONS, STATE_MAP
from src.actuators import Actuator, ManualButton
from src.mqtt_manager import MqttManager
from src.network_manager import NetworkManager
from src.sensors.sensor_classes import SENSOR_CLASSES


def load_config(file_path):
    """Load hardware configuration from a JSON file."""
    with open(file_path) as f:
        return json.load(f)


config = load_config("config.json")
CLIENT_ID = config["client_id"]


def on_message_received(topic, msg):
    """
    Callback triggered by MqttManager.
    Topic expected: client_id/category/target_id/action
    """
    try:
        topic_str = topic.decode()
        msg_str = msg.decode()
        print(
            f"Received MQTT message on topic: {topic_str} with payload: {msg.decode()}"
        )
        parts = topic_str.split("/")
        if len(parts) < 4:
            return

        category = parts[1]
        target_id = parts[2]
        action = msg_str

        if category == "actuators":
            target = actuators.get(target_id)
            if target and action in ALLOWED_ACTUATOR_ACTIONS:
                method = getattr(target, action)
                method()
                mqtt_mgr.publish(
                    f"{CLIENT_ID}/data",
                    {
                        "actuator": target_id,
                        "data": {"state": STATE_MAP[target.is_on()]},
                    },
                )

        elif category == "sensors" and action == "read":
            target = sensors.get(target_id)
            if target:
                mqtt_mgr.publish(
                    f"{CLIENT_ID}/data", {"sensor": target_id, "data": target.read()}
                )

    except Exception as e:
        print(f"Routing error: {e}")


wifi_mgr = NetworkManager(secrets.get("WIFI_SSID"), secrets.get("WIFI_PASSWORD"))
mqtt_mgr = MqttManager(
    client_id=CLIENT_ID,
    broker_ip=secrets.get("MQTT_BROKER"),
    user=secrets.get("MQTT_USER"),
    password=secrets.get("MQTT_PASSWORD"),
)
mqtt_mgr.set_callback(on_message_received)

sensors = {}
for item in config["sensors"]:
    cls = SENSOR_CLASSES.get(item["type"])
    if cls:
        args = {"pin_number": item["pin"], "sensor_id": item["id"]}
        # TODO: Find more elegant way to handle sensor-specific
        # parameters without hardcoding keys
        if "calibration" in item:
            args["calibration"] = item["calibration"]

        sensors[item["id"]] = cls(**args)

actuators = {}
for item in config["actuators"]:
    actuators[item["id"]] = Actuator(item["pin"], item["id"])

buttons = []
for item in config["buttons"]:
    btn = ManualButton(item["pin"], item["id"], item["target"])
    buttons.append(btn)


async def monitor_buttons():
    """Task to check buttons frequently (non-blocking)."""
    while True:
        for btn in buttons:
            if btn.is_pressed():
                target = actuators.get(btn.target_id)
                if target:
                    target.toggle()
                    # Debounce: wait until button is released or small delay
                    await asyncio.sleep(0.3)
        # Very short sleep to let other tasks run
        await asyncio.sleep(0.05)


async def read_sensors():
    """Task to read all registered sensors dynamically."""
    while True:
        data_payload = {}
        # Iterate over the instances (values), not the keys (strings)
        for sensor_instance in sensors.values():
            # Now sensor_instance is the object, and has the .read() method
            measurements = sensor_instance.read()
            data_payload[sensor_instance.sensor_id] = measurements

        print(f"Data Collected: {data_payload}")
        await asyncio.sleep(3)


async def mqtt_listen_task():
    """Polls the broker for incoming commands."""
    while True:
        if wifi_mgr.wlan.isconnected():
            mqtt_mgr.check_msg()
        await asyncio.sleep(0.1)


async def telemetry_task():
    """Reads sensors and publishes to MQTT every 10 seconds."""
    while True:
        data_payload = {}
        # We read our standardized sensors
        for sensor_id, sensor in sensors.items():
            data_payload[sensor_id] = sensor.read()

        # We also add actuators state
        actuators_state = {}
        for act_id, act in actuators.items():
            actuators_state[act_id] = "ON" if act.is_on() else "OFF"
        data_payload["actuators"] = actuators_state

        if wifi_mgr.wlan.isconnected():
            mqtt_mgr.publish(f"{CLIENT_ID}/telemetry", data_payload)
            print(f"Published: {data_payload}")

        await asyncio.sleep(10)


async def main():
    """Orchestrator for all asynchronous tasks."""
    print("System Starting...")
    # 1. Connect Wi-Fi
    if await wifi_mgr.connect():
        # 2. Connect MQTT
        await mqtt_mgr.connect()

    # 3. Start all concurrent tasks
    await asyncio.gather(
        monitor_buttons(),
        telemetry_task(),
        mqtt_listen_task(),
        wifi_mgr.keep_connected(),
    )


# Start the event loop
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("System Stopped")
