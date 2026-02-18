from machine import Pin


class Actuator:
    """Generic ON/OFF device controlled via GPIO."""

    # TODO: Add parameters for different actuator types
    # (e.g., PWM for dimmers, etc.) in the future.

    def __init__(self, pin_number, actuator_id):
        self.id = actuator_id
        self.pin = Pin(pin_number, Pin.OUT)
        self.off()  # Ensure safe state at startup

    def on(self):
        """Enable the actuator."""
        print(f"Turning ON actuator {self.id} (Pin {self.pin})")
        self.pin.value(0)

    def off(self):
        """Disable the actuator."""
        print(f"Turning OFF actuator {self.id} (Pin {self.pin})")
        self.pin.value(1)

    def toggle(self):
        """Invert the current state of the actuator."""
        print(f"Toggling actuator {self.id} (Pin {self.pin}), \
            state: {'ON' if self.pin.value() else 'OFF'}")
        self.pin.value(not self.pin.value())

    def is_on(self):
        """Check if the actuator is active."""
        return not bool(self.pin.value())


class ManualButton:
    """Input handler for a physical push button."""

    # TODO: Define button in config with target actuator
    # and possibly debounce settings in the future.
    def __init__(self, pin_number, button_id, target_id):
        self.id = button_id
        self.target_id = target_id  # The ID of the actuator it controls
        self.pin = Pin(pin_number, Pin.IN, Pin.PULL_UP)

    def is_pressed(self):
        """Check button state (active low)."""
        return self.pin.value() == 0
