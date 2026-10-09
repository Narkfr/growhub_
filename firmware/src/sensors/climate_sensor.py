import dht
from constants import HUMIDITY_MAX_PERCENT, HUMIDITY_MIN_PERCENT
from machine import Pin

from .base import BaseSensor


class ClimateSensor(BaseSensor):
    """
    Driver for the DHT11 Temperature and Humidity sensor.

    Performs a single measurement attempt; retry and pacing are handled by
    the async orchestrator (app.py) so this never blocks the event loop.
    """

    def __init__(self, pin_number, sensor_id):
        super().__init__(pin_number, sensor_id)
        self.sensor = dht.DHT11(Pin(pin_number))

    def read(self):
        """
        Attempt a single temperature/humidity measurement.
        Returns a dict, or None if the measurement failed.
        """
        try:
            self.sensor.measure()
            temp = self.sensor.temperature()
            hum = self.sensor.humidity()

            # Validate temperature is a number
            if not isinstance(temp, (int, float)):  # noqa: UP038
                raise ValueError(f"Invalid temperature: {temp}")

            # Validate humidity is within plausible bounds
            if not isinstance(hum, (int, float)) or not (  # noqa: UP038
                HUMIDITY_MIN_PERCENT <= hum <= HUMIDITY_MAX_PERCENT
            ):
                raise ValueError(f"Invalid humidity: {hum}")

            return {
                "temperature": {"value": temp, "unit": "celsius"},
                "humidity": {"value": hum, "unit": "percent"},
            }
        except (OSError, ValueError) as e:
            print(f"DHT11 Error: {e}")
            return None
