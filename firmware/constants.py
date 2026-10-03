ALLOWED_ACTUATOR_ACTIONS = ["on", "off", "toggle"]
ALLOWED_SENSOR_ACTIONS = ["read"]

# Telemetry publishing interval (seconds). 30 s is plenty for greenhouse
# monitoring; 1 Hz generated far more data than the system needs.
TELEMETRY_INTERVAL_SECONDS = 30
