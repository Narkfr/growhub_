# GrowHub hardware manifest template.
#
# Copy this file to `manifest.py` and adjust the pins/ids to match your
# wiring. The real `manifest.py` is machine-specific and is NOT committed
# (it is gitignored).

MANIFEST = {
    # Nom du modèle annoncé au serveur (topic info).
    "model": "Bourgeon V1",
    "display": {
        "type": "ssd1306",
        "width": 128,
        "height": 64,
        "i2c": {"id": 0, "sda": 4, "scl": 5},
        "addr": 0x3C,
        # Ce que l'écran montre : chaque entrée est une mesure nommée.
        # Omis, on retombe sur température + humidité du premier capteur qui les
        # publie (comportement historique). Deux lignes tiennent sous le titre
        # sur un écran 128x64 ; au-delà, l'affichage tourne par pages.
        "title": "BOURGEON",
        "fields": [
            {
                "source": "ClimateSensor",
                "metric": "temperature",
                "label": "Temp",
                "decimals": 1,
            },
            {
                "source": "ClimateSensor",
                "metric": "humidity",
                "label": "Hum",
                "decimals": 0,
            },
            {
                "source": "SoilSensor",
                "metric": "moisture",
                "label": "Sol",
                "decimals": 0,
            },
            {"kind": "actuator", "source": "WaterPump", "label": "Pompe"},
        ],
    },
    "actuators": [
        {"id": "WaterPump", "pin": 18, "active_low": True},
        {"id": "GrowLamp", "pin": 19, "active_low": True},
    ],
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
        {"id": "ClimateSensor", "type": "dht11", "pin": 16},
    ],
}
