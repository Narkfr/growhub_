import asyncio

from src.actuators import Actuator, ManualButton, load_config
from src.sensors.climate_sensor import ClimateSensor
from src.sensors.soil_sensor import SoilSensor

config = load_config("config.json")

climate = ClimateSensor(pin_number=config["sensors"][1]["pin"])
soil = SoilSensor(
    pin_number=config["sensors"][0]["pin"],
    dry_value=config["sensors"][0]["calibration"]["dry"],
    wet_value=config["sensors"][0]["calibration"]["wet"],
)

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
    """Task to read sensors every 3 seconds (non-blocking)."""
    while True:
        temp, hum = climate.read_data()
        moisture = soil.read_percentage()

        print("-" * 30)
        if temp is not None:
            print(f"Air: {temp}C | {hum}%")
        else:
            print("Air: Sensor Error")

        print(f"Soil Moisture: {moisture}%")

        # This sleep is non-blocking! Other tasks continue to run.
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
