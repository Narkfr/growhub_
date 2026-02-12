from machine import ADC, Pin


class SoilSensor:
    """
    Driver for the Capacitive Soil Moisture Sensor V2.0.
    Handles raw ADC readings and percentage conversion based on calibration.
    """

    def __init__(self, pin_number, dry_value=65535, wet_value=0):
        try:
            self.adc = ADC(Pin(pin_number))
            self.dry_value = dry_value
            self.wet_value = wet_value
        except (ValueError, OSError) as e:
            raise ValueError(f"Failed to initialize sensor on \
                             pin {pin_number}: {e}") from e

    def read_raw(self):
        """Returns the raw 16-bit value (0-65535)."""
        try:
            raw_value = self.adc.read_u16()
            if not (
                min(self.wet_value, self.dry_value)
                <= raw_value
                <= max(self.wet_value, self.dry_value)
            ):
                raise ValueError(
                    f"Raw value {raw_value} is outside calibration range [ \
                    {min(self.wet_value, self.dry_value)}, \
                    {max(self.wet_value, self.dry_value)}]"
                )
            return raw_value
        except OSError as e:
            raise OSError(f"Failed to read ADC: {e}") from e

    def get_percentage_from_raw(self, raw_value):
        """
        Pure logic: Converts a raw ADC value to a percentage.
        Formula: ((raw - dry) / (wet - dry)) * 100
        """
        if not isinstance(raw_value, int | float):
            raise TypeError(f"raw_value must be numeric, got {type(raw_value)}")

        if self.dry_value == self.wet_value:
            raise ValueError(
                "Calibration error: dry_value and wet_value cannot be equal"
            )

        percentage = (
            (raw_value - self.dry_value) / (self.wet_value - self.dry_value) * 100
        )
        percentage = max(0.0, min(100.0, round(percentage, 1)))

        return percentage

    def read_percentage(self):
        """Hardware dependent: Reads from ADC and then converts."""
        try:
            return self.get_percentage_from_raw(self.read_raw())
        except (OSError, TypeError) as e:
            raise RuntimeError(f"Failed to read sensor percentage: {e}") from e
