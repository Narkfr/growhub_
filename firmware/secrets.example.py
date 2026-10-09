# Gabarit du fichier secrets.py (à copier sous ce nom, il n'est pas versionné).
#
# Ne jamais écrire ici les identifiants définitifs d'un boîtier appairé : ils
# sont reçus par MQTT et enregistrés par le firmware dans creds.json,
# précisément pour qu'ils ne traînent pas dans un fichier qu'on édite à la main.
#
# Le snippet exact (identifiant, compte d'amorçage, code d'appairage) est
# produit par :
#
#     venv/bin/python gateway/backend/manage.py provision_device ghb-xxxxxx \
#         --secrets-path firmware/secrets.py
secrets = {
    # Wi-Fi
    "WIFI_SSID": "your_wifi_ssid_here",
    "WIFI_PASSWORD": "your_wifi_password_here",
    # Broker
    "MQTT_BROKER": "broker_ip_address_here",
    "MQTT_PORT": 1883,
    # Compte d'amorçage : sert uniquement à obtenir l'appairage, il est révoqué
    # automatiquement dès la première trame du boîtier.
    "MQTT_USER": "boot-ghb-xxxxxx",
    "MQTT_PASSWORD": "bootstrap_password_here",
    # Identité : le serveur enregistre le boîtier sous cet identifiant.
    "DEVICE_ID": "ghb-xxxxxx",
    # Code affiché à l'écran et saisi dans l'application.
    "PAIRING_CODE": "XXXXXX",
}
