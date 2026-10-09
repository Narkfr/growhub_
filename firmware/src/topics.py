"""Contrat de topics GrowHub v1 — miroir embarqué de docs/mqtt-topics.md.

Aucun topic n'est construit à la main ailleurs dans le firmware : ce module est
le seul endroit où le contrat est écrit, côté boîtier comme côté serveur
(``gateway/backend/growhub/topics.py``).
"""

PREFIX = "growhub"
VERSION = "v1"


def _device_topic(device_id, *parts):
    return "/".join((PREFIX, VERSION, device_id) + parts)


def telemetry(device_id):
    return _device_topic(device_id, "telemetry")


def state(device_id):
    return _device_topic(device_id, "state")


def status(device_id):
    return _device_topic(device_id, "status")


def info(device_id):
    return _device_topic(device_id, "info")


def ack(device_id):
    return _device_topic(device_id, "ack")


def cmd(device_id, category):
    return _device_topic(device_id, "cmd", category)


def cmd_actuators(device_id):
    return cmd(device_id, "actuators")


def cmd_sensors(device_id):
    return cmd(device_id, "sensors")


def cmd_config(device_id):
    return cmd(device_id, "config")


def command_topics(device_id):
    """Topics que le boîtier écoute en mode normal."""
    return [cmd_actuators(device_id), cmd_sensors(device_id), cmd_config(device_id)]


def provision(device_id):
    """Le boîtier s'y annonce (retained) pour réclamer son appairage."""
    return f"{PREFIX}/{VERSION}/provision/{device_id}"


def provision_credentials(device_id):
    """Le serveur y dépose les identifiants définitifs (retained)."""
    return f"{PREFIX}/{VERSION}/provision/{device_id}/creds"


def is_provision_credentials(device_id, topic):
    return topic == provision_credentials(device_id)


def is_command(device_id, topic):
    return topic in command_topics(device_id)


def command_category(device_id, topic):
    """``actuators``, ``sensors`` ou ``config`` pour un topic de commande."""
    for category in ("actuators", "sensors", "config"):
        if topic == cmd(device_id, category):
            return category
    return None
