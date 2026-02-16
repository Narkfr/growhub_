from machine import ADC, Pin

from .base import BaseSensor


class SoilSensor(BaseSensor):
    """
    Driver for the Capacitive Soil Moisture Sensor V2.0.
    Handles raw ADC readings and percentage conversion based on calibration.
    """

    def __init__(self, pin_number, sensor_id, calibration):
        try:
            super().__init__(pin_number, sensor_id)
            self.adc = ADC(Pin(pin_number))
            self.calibration = calibration
        except (ValueError, OSError) as e:
            raise ValueError(f"Failed to initialize sensor on \
                             pin {pin_number}: {e}") from e

    def read_raw(self):
        """Returns the raw 16-bit value (0-65535)."""
        try:
            raw_value = self.adc.read_u16()
            if not (
                min(self.calibration["wet"], self.calibration["dry"])
                <= raw_value
                <= max(self.calibration["wet"], self.calibration["dry"])
            ):
                raise ValueError(
                    f"Raw value {raw_value} is outside calibration range [ \
                    {min(self.calibration['wet'], self.calibration['dry'])}, \
                    {max(self.calibration['wet'], self.calibration['dry'])}]"
                )
            return raw_value
        except OSError as e:
            raise OSError(f"Failed to read ADC: {e}") from e

    def get_percentage_from_raw(self, raw_value):
        """
        Pure logic: Converts a raw ADC value to a percentage.
        Formula: ((raw - dry) / (wet - dry)) * 100
        """
        if not isinstance(raw_value, (int, float)):  # noqa: UP038
            raise TypeError(f"raw_value must be numeric, got {type(raw_value)}")

        if self.calibration["dry"] == self.calibration["wet"]:
            raise ValueError("Calibration error: dry and wet cannot be equal")

        percentage = (
            (raw_value - self.calibration["dry"])
            / (self.calibration["wet"] - self.calibration["dry"])
            * 100
        )
        percentage = max(0.0, min(100.0, round(percentage, 1)))

        return percentage

    def read(self):
        """Hardware dependent: Reads from ADC and then converts."""
        try:
            percentage = self.get_percentage_from_raw(self.read_raw())
            return {"moisture": {"value": percentage, "unit": "percent"}}
        except (OSError, TypeError) as e:
            raise RuntimeError(f"Failed to read sensor percentage: {e}") from e
