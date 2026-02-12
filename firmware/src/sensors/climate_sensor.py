import time

import dht
from machine import Pin


class ClimateSensor:
    """
    Driver for the DHT11 Temperature and Humidity sensor.
    Includes retry logic to handle common 'OSError: [Errno 110] ETIMEDOUT'.
    """

    def __init__(self, pin_number):
        self.sensor = dht.DHT11(Pin(pin_number))

    def read_data(self, retries=3):
        """
        Attempts to read temperature and humidity.
        Returns a tuple (temp, hum) or (None, None) if all retries fail.
        """
        for i in range(retries):
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

                return temp, hum
            except (OSError, ValueError) as e:
                print(f"DHT11 Error (attempt {i + 1}/{retries}): {e}")
                time.sleep(2)

        return None, None
