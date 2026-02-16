import asyncio
import json

from src.actuators import Actuator, ManualButton
from src.sensors.sensor_classes import SENSOR_CLASSES


def load_config(file_path):
    """Load hardware configuration from a JSON file."""
    with open(file_path) as f:
        return json.load(f)


config = load_config("config.json")

sensors = {}
for item in config["sensors"]:
    cls = SENSOR_CLASSES.get(item["type"])
    if cls:
        args = {"pin_number": item["pin"], "sensor_id": item["id"]}
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


async def main():
    """Orchestrator for all asynchronous tasks."""
    print("System Starting...")
    # Launch both tasks concurrently
    await asyncio.gather(monitor_buttons(), read_sensors())


# Start the event loop
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("System Stopped")
