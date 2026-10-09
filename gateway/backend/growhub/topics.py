"""MQTT topic contract, versioned. See docs/mqtt-topics.md.

The topics are rooted on the hardware device id, never on a user or an
account: ownership lives in the database, so a device can change hands without
rewriting any topic.
"""

ROOT = "growhub/v1"

DEVICE_TOPICS = ("info", "telemetry", "state", "status", "ack")
COMMAND_KINDS = ("actuators", "sensors", "config")


def device_topic(device_id, leaf):
    return f"{ROOT}/{device_id}/{leaf}"


def command_topic(device_id, kind):
    return f"{ROOT}/{device_id}/cmd/{kind}"


def provision_topic(device_id):
    return f"{ROOT}/provision/{device_id}"


def provision_credentials_topic(device_id):
    return f"{ROOT}/provision/{device_id}/creds"


def subscription_filter(leaf):
    """Broker filter matching `leaf` for every device (used by the worker)."""
    return f"{ROOT}/+/{leaf}"
