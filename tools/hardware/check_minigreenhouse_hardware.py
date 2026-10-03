"""
Hardware validation for the GrowHub sensors.

Run this ON the Pico (MicroPico "Run" command) with the `firmware/` folder
as the project root so `src.sensors.*` resolves. It reads both sensors a few
times so you can verify wiring and calibration in one go.
"""

import time

from src.sensors.climate_sensor import ClimateSensor
from src.sensors.soil_sensor import SoilSensor

# Update these with YOUR calibration values from soil_calibration.py.
DRY_VAL = 48859  # Example (air)
WET_VAL = 18308  # Example (water)

# Initialize sensors
soil = SoilSensor(
    pin_number=26,
    sensor_id="SoilSensor",
    calibration={"dry": DRY_VAL, "wet": WET_VAL},
)
climate = ClimateSensor(pin_number=15, sensor_id="ClimateSensor")

print("--- Starting Integrated Hardware Check ---")

for _ in range(5):
    climate_data = climate.read()
    soil_data = soil.read()

    print("-" * 30)
    if climate_data:
        temp = climate_data["temperature"]["value"]
        hum = climate_data["humidity"]["value"]
        print(f"Air: {temp}°C | {hum}%")
    else:
        print("Air: Sensor Error")

    print(f"Soil Moisture: {soil_data['moisture']['value']}%")
    time.sleep(3)

print("--- Check Finished ---")
