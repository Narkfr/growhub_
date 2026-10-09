"""Constantes du firmware Bourgeon.

Règle : toute valeur qui porte un sens — une durée, un seuil, un libellé montré
à l'utilisateur, un défaut de câblage, une chaîne de protocole — vit ici. Les
nombres qui ne sont que de l'arithmétique ou des indices de boucle restent dans
le code.

Les valeurs surchargeables à chaud (intervalle de télémétrie) ont une borne
minimale : c'est ce garde-fou qui empêche une commande de configuration
d'épuiser la batterie ou de saturer le broker.
"""

# -- Identité et version ------------------------------------------------------

FW_VERSION = "2.0.0"
MODEL = "Bourgeon V1"

DEVICE_ID_PREFIX = "ghb-"
# Les 6 DERNIERS caractères hexadécimaux de l'identifiant matériel : les premiers
# octets d'un Pico W à l'autre se ressemblent trop pour distinguer les boîtiers.
DEVICE_ID_HEX_LENGTH = 6

CREDENTIALS_PATH = "creds.json"
PAIRING_CODE_PLACEHOLDER = "----"

# -- Protocole MQTT -----------------------------------------------------------

MQTT_TOPIC_PREFIX = "growhub"
MQTT_TOPIC_VERSION = "v1"
MQTT_DEFAULT_PORT = 1883
MQTT_KEEPALIVE_SECONDS = 60
MQTT_CONNECT_TIMEOUT_SECONDS = 5
# QoS 0 assumé : en QoS 1, `umqtt.simple` bloque en attendant l'accusé.
MQTT_QOS = 0

# -- Cadences et temporisations (secondes, sauf mention) ----------------------

TELEMETRY_INTERVAL_SECONDS = 30
MIN_TELEMETRY_INTERVAL_SECONDS = 5
SENSOR_READ_RETRIES = 3
SENSOR_RETRY_DELAY_SECONDS = 2
DISPLAY_REFRESH_SECONDS = 2
# L'écran relit les capteurs de son côté : une seule tentative suffit.
DISPLAY_SENSOR_READ_RETRIES = 1
LISTEN_POLL_SECONDS = 0.1
BUTTON_POLL_SECONDS = 0.05
BUTTON_DEBOUNCE_SECONDS = 0.3
MQTT_RETRY_SECONDS = 10
WIFI_RETRY_SECONDS = 30
WIFI_CONNECT_ATTEMPTS = 10
WIFI_CONNECT_ATTEMPT_SECONDS = 1
WATCHDOG_TIMEOUT_MS = 8000
WATCHDOG_FEED_SECONDS = 2

# -- Actions et états ---------------------------------------------------------

# Actions acceptées, en minuscules : elles sont appliquées par getattr(), donc
# toute action absente de ces listes est refusée avant d'atteindre le matériel.
ALLOWED_ACTUATOR_ACTIONS = ["on", "off", "toggle"]
ALLOWED_SENSOR_ACTIONS = ["read"]
ALLOWED_CONFIG_ACTIONS = ["set"]

# États publiés sur MQTT (contrat) et leur écriture à l'écran (présentation).
ACTUATOR_STATE_ON = "ON"
ACTUATOR_STATE_OFF = "OFF"
ACTUATOR_STATE_LABELS = {ACTUATOR_STATE_ON: "Allumé", ACTUATOR_STATE_OFF: "Éteint"}

# -- Écran --------------------------------------------------------------------

SCREEN_TITLE = "BOURGEON"
SCREEN_LINE_HEIGHT = 20
SCREEN_FIRST_LINE_Y = 20
SCREEN_PAGE_INDICATOR_X = 100
SCREEN_DECIMALS_DEFAULT = 1

# Unités publiées par les capteurs -> ce qu'on écrit sur la dalle.
UNIT_LABELS = {
    "celsius": "°C",
    "percent": "%",
    "lux": "lux",
}

# Champs montrés quand le manifeste n'en déclare pas : le comportement
# historique (température et humidité du premier capteur qui les publie).
SCREEN_FIELDS_DEFAULT = (
    {"source": "auto", "metric": "temperature", "label": "Temp", "decimals": 1},
    {"source": "auto", "metric": "humidity", "label": "Hum", "decimals": 0},
)

# Défauts de câblage de la dalle SSD1306, utilisés si le manifeste est muet.
DISPLAY_DEFAULT_WIDTH = 128
DISPLAY_DEFAULT_HEIGHT = 64
DISPLAY_DEFAULT_ADDR = 0x3C
DISPLAY_I2C_ID = 0
DISPLAY_I2C_SDA = 4
DISPLAY_I2C_SCL = 5
DISPLAY_I2C_FREQ = 400000

# -- Capteurs -----------------------------------------------------------------

# Bornes de plausibilité : hors de ces valeurs, la mesure est rejetée comme
# aberrante plutôt que publiée.
HUMIDITY_MIN_PERCENT = 0
HUMIDITY_MAX_PERCENT = 100
SOIL_PERCENT_MIN = 0.0
SOIL_PERCENT_MAX = 100.0
SOIL_PERCENT_DECIMALS = 1
