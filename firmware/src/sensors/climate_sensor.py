import dht
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

            # Validate humidity is between 0 and 100
            if not isinstance(hum, (int, float)) or not (0 <= hum <= 100):  # noqa: UP038
                raise ValueError(f"Invalid humidity: {hum}")

            return {
                "temperature": {"value": temp, "unit": "celsius"},
                "humidity": {"value": hum, "unit": "percent"},
            }
        except (OSError, ValueError) as e:
            print(f"DHT11 Error: {e}")
            return None
