"""Identité du Bourgeon : dérivation matérielle et fichier d'identifiants."""

import json as _json

# Les modules MicroPython (dont ujson, machine, ubinascii) sont installés une
# seule fois par tests/firmware/conftest.py : les réinstaller ici écrasait les
# mocks des autres fichiers de test, pytest important tous les modules avant
# d'exécuter le premier.
from src import identity  # noqa: E402


def test_derived_device_id_uses_last_hex_characters():
    # Les premiers octets d'un Pico W sont communs : ce sont les derniers qui
    # distinguent deux boîtiers.
    assert identity.derived_device_id() == "ghb-060708"


def test_derived_ids_differ_when_only_the_tail_differs():
    first = identity.derived_device_id(b"\x01\x02\x03\x04\x05\x06\x07\x08")
    second = identity.derived_device_id(b"\x01\x02\x03\x04\x05\x06\x07\xff")
    assert first != second


def test_derived_device_id_accepts_non_bytes_identifiers():
    assert identity.derived_device_id("aabbccddeeff") == "ghb-ddeeff"


def test_resolve_device_id_prefers_provisioned_identity():
    assert identity.resolve_device_id({"DEVICE_ID": "ghb-3f2a91"}) == "ghb-3f2a91"


def test_resolve_device_id_falls_back_to_hardware():
    assert identity.resolve_device_id({}) == "ghb-060708"


def test_load_credentials_absent(tmp_path):
    assert identity.load_credentials(str(tmp_path / "creds.json")) is None


def test_load_credentials_incomplete(tmp_path):
    path = tmp_path / "creds.json"
    path.write_text(_json.dumps({"username": "ghb-3f2a91"}))
    assert identity.load_credentials(str(path)) is None


def test_load_credentials_reads_saved_file(tmp_path):
    path = str(tmp_path / "creds.json")
    identity.save_credentials("ghb-3f2a91", "secret", "broker.local", 1883, path=path)
    assert identity.load_credentials(path) == {
        "username": "ghb-3f2a91",
        "password": "secret",
        "broker": "broker.local",
        "port": 1883,
    }


def test_load_credentials_survives_corrupted_file(tmp_path):
    path = tmp_path / "creds.json"
    path.write_text("{pas du json")
    assert identity.load_credentials(str(path)) is None


def test_credentials_from_secrets_uses_bootstrap_account():
    credentials = identity.credentials_from_secrets(
        {"MQTT_USER": "boot-ghb-3f2a91", "MQTT_PASSWORD": "pw", "MQTT_BROKER": "b"}
    )
    assert credentials == {
        "username": "boot-ghb-3f2a91",
        "password": "pw",
        "broker": "b",
        "port": 1883,
    }
