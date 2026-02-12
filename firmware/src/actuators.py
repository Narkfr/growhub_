import json

from machine import Pin


class Actuator:
    """Generic ON/OFF device controlled via GPIO."""

    def __init__(self, pin_number, actuator_id):
        self.id = actuator_id
        self.pin = Pin(pin_number, Pin.OUT)
        self.off()  # Ensure safe state at startup

    def on(self):
        """Enable the actuator."""
        print(f"Turning ON actuator {self.id} (Pin {self.pin})")
        self.pin.value(1)

    def off(self):
        """Disable the actuator."""
        print(f"Turning OFF actuator {self.id} (Pin {self.pin})")
        self.pin.value(0)

    def toggle(self):
        """Invert the current state of the actuator."""
        print(f"Toggling actuator {self.id} (Pin {self.pin})")
        self.pin.value(not self.pin.value())

    def is_on(self):
        """Check if the actuator is active."""
        print(f"Actuator {self.id} state: {'ON' if self.pin.value() else 'OFF'}")
        return bool(self.pin.value())


class ManualButton:
    """Input handler for a physical push button."""

    def __init__(self, pin_number, button_id, target_id):
        self.id = button_id
        self.target_id = target_id  # The ID of the actuator it controls
        self.pin = Pin(pin_number, Pin.IN, Pin.PULL_UP)

    def is_pressed(self):
        """Check button state (active low)."""
        print(
            f"Button {self.id} state: \
            {'Pressed' if self.pin.value() == 0 else 'Released'}"
        )
        return self.pin.value() == 0


def load_config(file_path):
    """Load hardware configuration from a JSON file."""
    with open(file_path) as f:
        return json.load(f)
