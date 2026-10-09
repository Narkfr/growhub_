"""Broker file handling, anchored on a vector produced by the real tool."""

import base64
import os
import stat

import pytest
from telemetry.mosquitto import (
    ACL_FILE_MODE,
    PASSWORD_FILE_MODE,
    BrokerFiles,
    bootstrap_username,
    generate_password,
    hash_password,
    parse_password_file,
    render_acl,
    render_password_file,
)

pytestmark = pytest.mark.django_db


def test_hash_matches_mosquitto_passwd_output():
    """Vector generated with mosquitto_passwd 2.0.21 (-c -b), then reproduced here.

    Verified byte for byte during development: this is what guarantees the Pico's
    credentials are accepted by the broker without shelling out to the tool.
    """
    password_hash = hash_password(
        "S3cret-Test-Pw", salt=base64.b64decode("5O4UEM9mm5IDNSqZ"), iterations=101
    )
    assert password_hash == (
        "$7$101$5O4UEM9mm5IDNSqZ$"
        "Ful3iYVO3ilFbYEPCW9Y/QMPLvlOLiOn1wRxEoWnoTctB47B+vUWCt5BC84uCs5l7SHNOhCkKnErlm9oqjaJDQ=="
    )


def test_hash_is_salted_and_unique():
    first = hash_password("meme-mot-de-passe")
    second = hash_password("meme-mot-de-passe")
    assert first != second
    assert first.startswith("$7$101$")
    assert len(first.split("$")[3]) == 16  # 12-byte salt in base64


def test_generated_password_is_long_enough():
    passwords = {generate_password() for _ in range(20)}
    assert len(passwords) == 20
    assert min(len(password) for password in passwords) >= 24


def test_password_file_round_trip():
    text = render_password_file(
        {"ghb-3f2a91": "$7$101$aaa$bbb", "growhub_api": "$7$101$ccc$ddd"}
    )
    assert text.startswith("# Fichier généré")
    assert parse_password_file(text) == {
        "ghb-3f2a91": "$7$101$aaa$bbb",
        "growhub_api": "$7$101$ccc$ddd",
    }
    assert parse_password_file("# commentaire\n\nligne-pourrie\n") == {}


def test_acl_grants_devices_their_own_prefix_only():
    acl = render_acl("growhub_api")
    assert "user growhub_api" in acl
    assert "topic read growhub/v1/+/telemetry" in acl
    assert "topic write growhub/v1/+/cmd/#" in acl
    # Le motif %u remplace le nom d'utilisateur, donc le device_id.
    assert "pattern write growhub/v1/%u/telemetry" in acl
    assert "pattern read growhub/v1/%u/cmd/#" in acl
    assert "boot-" not in acl


def test_acl_adds_bootstrap_block_only_while_pairing():
    acl = render_acl("growhub_api", ["ghb-3f2a91"])
    assert f"user {bootstrap_username('ghb-3f2a91')}" in acl
    assert "topic write growhub/v1/provision/ghb-3f2a91" in acl
    assert "topic read growhub/v1/provision/ghb-3f2a91/creds" in acl


def test_broker_files_write_users_with_tight_permissions():
    broker = BrokerFiles()
    password, password_hash = broker.set_password("ghb-3f2a91")
    assert password and password_hash.startswith("$7$")

    users = broker.read_users()
    assert users == {"ghb-3f2a91": password_hash}
    mode = stat.S_IMODE(os.stat(broker.password_file).st_mode)
    assert mode == PASSWORD_FILE_MODE

    assert broker.remove_user("ghb-3f2a91") is True
    assert broker.read_users() == {}
    assert broker.remove_user("ghb-3f2a91") is False


def test_broker_files_write_acl_and_reload():
    broker = BrokerFiles()
    text = broker.write_acl(["ghb-7c1d02"])
    assert os.stat(broker.acl_file).st_mode & 0o777 == ACL_FILE_MODE
    assert text == broker.acl_file.read_text(encoding="utf-8")
    assert "ghb-7c1d02" in text

    # Pas de commande de rechargement configurée -> on ne prétend pas avoir rechargé.
    assert broker.reload() is False


def test_reload_reports_command_failure(settings):
    settings.GROWHUB = {**settings.GROWHUB, "MQTT_RELOAD_COMMAND": "false"}
    assert BrokerFiles().reload() is False

    settings.GROWHUB = {**settings.GROWHUB, "MQTT_RELOAD_COMMAND": "true"}
    assert BrokerFiles().reload() is True
