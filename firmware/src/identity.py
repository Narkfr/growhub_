"""Identité du Bourgeon : identifiant matériel et identifiants de connexion.

L'identifiant du boîtier est dérivé du microcontrôleur, jamais saisi à la main :
c'est ce qui garantit qu'un appareil ne peut pas se faire passer pour un autre
en changeant un fichier de configuration.
"""

from constants import CREDENTIALS_PATH, DEVICE_ID_PREFIX


def _hexlify(value):
    """Hexadécimal en minuscules, accepte aussi une chaîne déjà encodée."""
    if isinstance(value, str):
        return value.lower()
    try:
        import ubinascii

        return ubinascii.hexlify(value).decode()
    except ImportError:  # hôte de test sans ubinascii
        return "".join(f"{byte:02x}" for byte in value)


def derived_device_id(unique_id=None):
    """``ghb-`` suivi des 6 derniers caractères hexadécimaux de l'identifiant matériel.

    Les *derniers* octets sont retenus parce que les premiers se ressemblent d'un
    Pico W à l'autre (préfixe constructeur commun) et produiraient des collisions
    entre deux boîtiers.
    """
    if unique_id is None:
        import machine

        unique_id = machine.unique_id()
    return DEVICE_ID_PREFIX + _hexlify(unique_id)[-6:]


def resolve_device_id(secrets):
    """Identifiant provisionné s'il existe, sinon dérivé du matériel.

    Un boîtier provisionné porte l'identifiant enregistré côté serveur ; un
    boîtier neuf se présente sous son identité matérielle, que le serveur
    enregistre au provisioning.
    """
    return secrets.get("DEVICE_ID") or derived_device_id()


def load_credentials(path=CREDENTIALS_PATH):
    """Identifiants définitifs reçus à l'appairage, ou ``None``."""
    try:
        import ujson

        with open(path) as handle:
            data = ujson.load(handle)
    except (OSError, ValueError):
        return None
    if not data.get("username") or not data.get("password"):
        return None
    return data


def save_credentials(username, password, broker, port, path=CREDENTIALS_PATH):
    """Écrit les identifiants définitifs (remplace le compte d'amorçage)."""
    import ujson

    data = {
        "username": username,
        "password": password,
        "broker": broker,
        "port": int(port),
    }
    with open(path, "w") as handle:
        ujson.dump(data, handle)
    return data


def credentials_from_secrets(secrets):
    """Compte d'amorçage : sert uniquement à demander l'appairage."""
    return {
        "username": secrets.get("MQTT_USER"),
        "password": secrets.get("MQTT_PASSWORD"),
        "broker": secrets.get("MQTT_BROKER"),
        "port": int(secrets.get("MQTT_PORT", 1883)),
    }
