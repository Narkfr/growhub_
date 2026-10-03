MANIFEST = {
    # Used as a prefix: app.py appends a unique suffix from
    # machine.unique_id() so multiple GrowHubs don't collide on MQTT.
    "client_id": "GrowHubClient",
    "actuators": [{"id": "WaterPump", "pin": 18}, {"id": "GrowLamp", "pin": 19}],
    "buttons": [
        {"id": "WaterPumpButton", "pin": 14, "target": "WaterPump"},
        {"id": "GrowLampButton", "pin": 13, "target": "GrowLamp"},
    ],
    "sensors": [
        {
            "id": "SoilSensor",
            "type": "csmsv2",
            "pin": 26,
            "calibration": {"dry": 50000, "wet": 18000},
        },
        {"id": "ClimateSensor", "type": "dht11", "pin": 15},
    ],
}
