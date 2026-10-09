"""Le contrat de topics embarqué doit rester le miroir de docs/mqtt-topics.md."""

import sys
from pathlib import Path

_FIRMWARE = Path(__file__).resolve().parents[3] / "firmware"
if str(_FIRMWARE) not in sys.path:
    sys.path.insert(0, str(_FIRMWARE))

from src import topics  # noqa: E402

DEVICE = "ghb-3f2a91"


def test_device_topics():
    assert topics.telemetry(DEVICE) == "growhub/v1/ghb-3f2a91/telemetry"
    assert topics.state(DEVICE) == "growhub/v1/ghb-3f2a91/state"
    assert topics.status(DEVICE) == "growhub/v1/ghb-3f2a91/status"
    assert topics.info(DEVICE) == "growhub/v1/ghb-3f2a91/info"
    assert topics.ack(DEVICE) == "growhub/v1/ghb-3f2a91/ack"


def test_command_topics():
    assert topics.cmd_actuators(DEVICE) == "growhub/v1/ghb-3f2a91/cmd/actuators"
    assert topics.cmd_sensors(DEVICE) == "growhub/v1/ghb-3f2a91/cmd/sensors"
    assert topics.cmd_config(DEVICE) == "growhub/v1/ghb-3f2a91/cmd/config"
    assert topics.command_topics(DEVICE) == [
        "growhub/v1/ghb-3f2a91/cmd/actuators",
        "growhub/v1/ghb-3f2a91/cmd/sensors",
        "growhub/v1/ghb-3f2a91/cmd/config",
    ]


def test_provision_topics():
    assert topics.provision(DEVICE) == "growhub/v1/provision/ghb-3f2a91"
    assert (
        topics.provision_credentials(DEVICE) == "growhub/v1/provision/ghb-3f2a91/creds"
    )


def test_topic_helpers_recognise_theirs():
    assert topics.is_provision_credentials(DEVICE, topics.provision_credentials(DEVICE))
    assert not topics.is_provision_credentials(DEVICE, topics.provision(DEVICE))
    assert topics.is_command(DEVICE, topics.cmd_config(DEVICE))
    assert not topics.is_command(DEVICE, topics.telemetry(DEVICE))


def test_command_category():
    assert topics.command_category(DEVICE, topics.cmd_actuators(DEVICE)) == "actuators"
    assert topics.command_category(DEVICE, topics.cmd_sensors(DEVICE)) == "sensors"
    assert topics.command_category(DEVICE, topics.cmd_config(DEVICE)) == "config"
    assert topics.command_category(DEVICE, topics.telemetry(DEVICE)) is None


def test_topics_are_scoped_to_the_device():
    # Aucun topic d'un appareil ne doit pouvoir désigner un autre appareil.
    assert topics.telemetry("ghb-aaaaaa") != topics.telemetry("ghb-bbbbbb")
