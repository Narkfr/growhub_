import sys

# Adding src to path so we can import our classes
sys.path.append("sensors")

import time

from sensors.climate_sensor import ClimateSensor  # type: ignore
from sensors.soil_sensor import SoilSensor  # type: ignore

# Update these with YOUR calibration values from the previous step
DRY_VAL = 48859  # Example
WET_VAL = 18308  # Example

# Initialize sensors
soil = SoilSensor(pin_number=26, dry_value=DRY_VAL, wet_value=WET_VAL)
climate = ClimateSensor(pin_number=15)

print("--- Starting Integrated Hardware Check ---")

for _ in range(5):
    temp, hum = climate.read_data()
    raw_soil = soil.read_raw()
    moisture = soil.read_percentage()

    print("-" * 30)
    if temp is not None:
        print(f"Air: {temp}°C | {hum}%")
    else:
        print("Air: Sensor Error")

    print(f"Soil Moisture: {moisture}%")
    time.sleep(3)

print("--- Check Finished ---")
