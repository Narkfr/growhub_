"""Constantes du firmware Bourgeon.

Les valeurs surchargeables à chaud (intervalle de télémétrie) ont une borne
minimale : c'est ce garde-fou qui empêche une commande de configuration
d'épuiser la batterie ou de saturer le broker.
"""

FW_VERSION = "2.0.0"
MODEL = "Bourgeon V1"

# Actions acceptées, en minuscules : elles sont appliquées par getattr(), donc
# toute action absente de ces listes est refusée avant d'atteindre le matériel.
ALLOWED_ACTUATOR_ACTIONS = ["on", "off", "toggle"]
ALLOWED_SENSOR_ACTIONS = ["read"]
ALLOWED_CONFIG_ACTIONS = ["set"]

# Intervalle de télémétrie (secondes). 30 s suffit largement pour une serre ;
# 1 Hz produisait bien plus de données que nécessaire.
TELEMETRY_INTERVAL_SECONDS = 30
MIN_TELEMETRY_INTERVAL_SECONDS = 5

# Identité
DEVICE_ID_PREFIX = "ghb-"
CREDENTIALS_PATH = "creds.json"
