"""The firmware and the backend must never drift apart on the wire contract.

Both sides embed the same topic scheme (``firmware/src/topics.py`` and
``growhub/topics.py``) and the broker's ACL is generated from the backend's
view of it. This test loads the *firmware* module and confronts it with the
backend topics and the generated ACL, so a rename on one side fails here
instead of silently breaking a device in a greenhouse.
"""

import importlib.util
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from growhub import topics as backend_topics
from telemetry.mosquitto import render_acl

FIRMWARE_TOPICS = Path(__file__).resolve().parents[4] / "firmware" / "src" / "topics.py"
DEVICE = "ghb-3f2a91"
OTHER = "ghb-001122"


@pytest.fixture(scope="module")
def firmware():
    # `firmware/src/topics.py` lit ses constantes dans `firmware/constants.py` :
    # le dossier firmware doit être importable, comme pour ses propres tests.
    firmware_root = str(FIRMWARE_TOPICS.parents[1])
    if firmware_root not in sys.path:
        sys.path.insert(0, firmware_root)
    spec = importlib.util.spec_from_file_location("firmware_topics", FIRMWARE_TOPICS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- topics ------------------------------------------------------------------


def test_device_leaf_topics_agree(firmware):
    for leaf in backend_topics.DEVICE_TOPICS:
        assert getattr(firmware, leaf)(DEVICE) == backend_topics.device_topic(
            DEVICE, leaf
        ), leaf


def test_command_topics_agree(firmware):
    assert sorted(firmware.command_topics(DEVICE)) == sorted(
        backend_topics.command_topic(DEVICE, kind)
        for kind in backend_topics.COMMAND_KINDS
    )
    for kind in backend_topics.COMMAND_KINDS:
        assert firmware.cmd(DEVICE, kind) == backend_topics.command_topic(DEVICE, kind)


def test_provision_topics_agree(firmware):
    assert firmware.provision(DEVICE) == backend_topics.provision_topic(DEVICE)
    assert firmware.provision_credentials(
        DEVICE
    ) == backend_topics.provision_credentials_topic(DEVICE)


def test_backend_filters_match_the_firmware_topics(firmware):
    # L'ouvrier s'abonne aux filtres du serveur : ils doivent couvrir les topics
    # réellement publiés par un boîtier.
    for leaf in backend_topics.DEVICE_TOPICS:
        assert backend_topics.subscription_filter(leaf) == f"growhub/v1/+/{leaf}"
        assert firmware.__dict__[leaf](DEVICE).startswith("growhub/v1/")


# --- ACL ---------------------------------------------------------------------


def _device_permissions(acl_text):
    """Permissions of a paired device, ``%u`` replaced by its own id."""
    permissions = set()
    for line in acl_text.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0] == "pattern":
            access, pattern = parts[1], parts[2].replace("%u", DEVICE)
            if access == "readwrite":
                permissions |= {(pattern, "read"), (pattern, "write")}
            else:
                permissions.add((pattern, access))
    return permissions


def _matches(pattern, topic):
    """Sémantique des jokers MQTT : ``+`` un niveau, ``#`` la fin."""
    pattern_parts = pattern.split("/")
    topic_parts = topic.split("/")
    for index, part in enumerate(pattern_parts):
        if part == "#":
            return True
        if index >= len(topic_parts):
            return False
        if part not in ("+", topic_parts[index]):
            return False
    return len(pattern_parts) == len(topic_parts)


def _allows(permissions, topic, access):
    return any(
        perm == access and _matches(pattern, topic) for pattern, perm in permissions
    )


@pytest.fixture
def permissions():
    return _device_permissions(render_acl("growhub_api"))


def test_device_can_write_every_topic_it_publishes(firmware, permissions):
    published = [
        firmware.telemetry(DEVICE),
        firmware.state(DEVICE),
        firmware.status(DEVICE),
        firmware.info(DEVICE),
        firmware.ack(DEVICE),
    ]
    for topic in published:
        assert _allows(permissions, topic, "write"), topic


def test_device_can_read_every_topic_it_subscribes(firmware, permissions):
    for topic in firmware.command_topics(DEVICE):
        assert _allows(permissions, topic, "read"), topic


def test_device_patterns_all_use_the_username(permissions):
    # Aucune règle d'appareil ne doit viser un identifiant en dur : c'est ce qui
    # permet de n'avoir aucune entrée par appareil, et donc rien à regénérer.
    for pattern, _access in permissions:
        assert pattern.startswith(f"growhub/v1/{DEVICE}/")


def test_device_cannot_reach_another_device(firmware, permissions):
    foreign = [
        firmware.telemetry(OTHER),
        firmware.status(OTHER),
        firmware.ack(OTHER),
        firmware.cmd_actuators(OTHER),
    ]
    for topic in foreign:
        assert not _allows(permissions, topic, "write"), topic
        assert not _allows(permissions, topic, "read"), topic
    # Un appareil écrit ses commandes mais ne les lit pas.
    assert not _allows(permissions, firmware.cmd_actuators(DEVICE), "write")


def test_acl_never_grants_anything_to_the_other_device(permissions):
    assert not [entry for entry in permissions if OTHER in entry[0]]


def test_bootstrap_account_is_confined_to_its_own_pairing_topics():
    device_acl = render_acl("growhub_api", ["ghb-7c1d02"])
    assert "user boot-ghb-7c1d02" in device_acl
    assert "topic write growhub/v1/provision/ghb-7c1d02" in device_acl
    assert "topic read growhub/v1/provision/ghb-7c1d02/creds" in device_acl
    # Le compte d'amorçage ne doit apparaître ni dans les patterns d'appareil ni
    # ailleurs une fois révoqué.
    assert "boot-ghb-3f2a91" not in render_acl("growhub_api")


# --- charges utiles ----------------------------------------------------------


def test_firmware_telemetry_payload_shape_is_accepted(device):
    """La trame d'un vrai Bourgeon (seq + sensors + actuators, sans horodatage)."""
    from telemetry.services import handle_message

    topic = backend_topics.device_topic(device.device_id, "telemetry")
    payload = {
        "seq": 1,
        "sensors": {"ClimateSensor": {"temperature": {"value": 21.5}}},
        "actuators": {"WaterPump": "OFF"},
    }
    kind, obj = handle_message(topic, payload)
    assert kind == "telemetry"
    device.refresh_from_db()
    assert device.last_state["seq"] == 1
    assert device.last_state["actuators"] == {"WaterPump": "OFF"}


def test_firmware_state_payload_shape_is_accepted(device):
    from telemetry.services import handle_message

    topic = backend_topics.device_topic(device.device_id, "state")
    kind, _ = handle_message(topic, {"actuators": {"WaterPump": "ON"}})
    assert kind == "state"
    device.refresh_from_db()
    assert device.last_state["actuators"] == {"WaterPump": "ON"}


def test_firmware_ack_payload_closes_the_command(device, user):
    from telemetry.models import CommandAudit
    from telemetry.services import handle_message

    audit = CommandAudit.objects.create(
        cmd_id=uuid4(),
        device=device,
        user=user,
        kind="actuators",
        action="on",
        args={"target": "WaterPump"},
    )
    topic = backend_topics.device_topic(device.device_id, "ack")
    payload = {
        "cmd_id": str(audit.cmd_id),
        "ok": True,
        "error": "",
        "state": {"actuators": {"WaterPump": "ON"}},
    }
    kind, _ = handle_message(topic, payload)
    assert kind == "ack"
    audit.refresh_from_db()
    assert audit.acked_at is not None
