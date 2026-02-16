class BaseSensor:
    """Base class for all sensors to ensure a unified interface."""

    def __init__(self, pin_number, sensor_id):
        self.pin_number = pin_number
        self.sensor_id = sensor_id

    def read(self):
        """
        Should be implemented by subclasses.
        Must return a dictionary of measurements.
        """
        raise NotImplementedError("Subclasses must implement read()")
