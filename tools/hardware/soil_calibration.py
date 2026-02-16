# This script should be run via the "Run" button in VS Code
import time

from machine import ADC, Pin

# Sensor connected to GP26 (ADC0)
soil_pin = ADC(Pin(26))

print("--- Soil Sensor Calibration Utility ---")
print("1. Leave the sensor in open AIR. Wait for stability...")
time.sleep(2)
air_value = soil_pin.read_u16()
print(f"DRY Value (Air): {air_value}")

print("\n2. Dip the sensor in WATER (up to the white line). Wait...")
time.sleep(5)
water_value = soil_pin.read_u16()
print(f"WET Value (Water): {water_value}")

print("\n--- Calibration Complete ---")
print(f"Update your SoilSensor(26, dry_value={air_value}, wet_value={water_value})")
