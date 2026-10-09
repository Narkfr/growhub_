from constants import ACTUATOR_STATE_OFF, ACTUATOR_STATE_ON
from machine import Pin


class BaseActuator:
    """Generic ON/OFF device controlled via GPIO.

    `active_low` (default True) means "ON" drives the pin LOW — the common
    convention for relay modules. Set it to False for active-high devices.
    """

    # TODO: Add parameters for different actuator types
    # (e.g., PWM for dimmers, etc.) in the future.

    def __init__(self, pin_number, actuator_id, active_low=True):
        self.id = actuator_id
        self.active_low = active_low
        self.pin = Pin(pin_number, Pin.OUT)
        self.off()  # Ensure safe state at startup

    def on(self):
        """Enable the actuator."""
        print(f"Turning ON actuator {self.id} (Pin {self.pin})")
        self.pin.value(0 if self.active_low else 1)

    def off(self):
        """Disable the actuator."""
        print(f"Turning OFF actuator {self.id} (Pin {self.pin})")
        self.pin.value(1 if self.active_low else 0)

    def toggle(self):
        """Invert the current state of the actuator."""
        print(
            f"Toggling actuator {self.id} (Pin {self.pin}), state: {self.human_state()}"
        )
        self.pin.value(not self.pin.value())

    def is_on(self):
        """Check if the actuator is active."""
        level = self.pin.value()
        return (level == 0) if self.active_low else (level == 1)

    def human_state(self):
        """Return a human-readable state."""
        return ACTUATOR_STATE_ON if self.is_on() else ACTUATOR_STATE_OFF


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
