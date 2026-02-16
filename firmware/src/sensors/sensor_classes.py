from .climate_sensor import ClimateSensor
from .soil_sensor import SoilSensor

SENSOR_CLASSES = {"csmsv2": SoilSensor, "dht11": ClimateSensor}
