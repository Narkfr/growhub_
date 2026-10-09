"""Pairing handover: temporary account -> real credentials -> confirmed."""

import pytest
from devices.models import MqttCredential
from telemetry import provisioning
from telemetry.mosquitto import BrokerFiles, bootstrap_username
from telemetry.provisioning import ProvisioningError
from telemetry.services import handle_message

pytestmark = pytest.mark.django_db


def test_devices_awaiting_pairing_lists_open_claims(pending_device, device):
    assert provisioning.devices_awaiting_pairing() == [pending_device.device_id]


def test_bootstrap_account_is_written_to_broker_files(pending_device):
    username, password = provisioning.provision_bootstrap(pending_device)

    assert username == f"boot-{pending_device.device_id}"
    assert len(password) >= 24
    broker = BrokerFiles()
    assert username in broker.read_users()
    acl = broker.acl_file.read_text(encoding="utf-8")
    assert f"user {username}" in acl


def test_provision_device_refuses_an_unpaired_device(pending_device):
    with pytest.raises(ProvisioningError):
        provisioning.provision_device(pending_device)


def test_provision_device_publishes_credentials_retained(claimed_device, no_real_mqtt):
    credential, password = provisioning.provision_device(claimed_device)

    assert credential.username == claimed_device.device_id
    assert credential.password_hash.startswith("$7$101$")
    assert password not in credential.password_hash
    assert credential.installed_at is None

    assert claimed_device.device_id in BrokerFiles().read_users()

    message = no_real_mqtt.messages[-1]
    assert message["topic"] == f"growhub/v1/provision/{claimed_device.device_id}/creds"
    assert message["retain"] is True
    assert message["payload"]["username"] == claimed_device.device_id
    assert message["payload"]["password"] == password


def test_first_message_with_real_credentials_closes_the_pairing(
    claimed_device, no_real_mqtt
):
    provisioning.provision_bootstrap(claimed_device)
    provisioning.provision_device(claimed_device)
    no_real_mqtt.messages.clear()

    handle_message(
        f"growhub/v1/{claimed_device.device_id}/telemetry",
        {"sensors": {"ClimateSensor": {"temperature": 20}}},
    )

    credential = MqttCredential.objects.get(device=claimed_device)
    assert credential.installed_at is not None
    assert credential.bootstrap_revoked_at is not None
    assert (
        bootstrap_username(claimed_device.device_id) not in BrokerFiles().read_users()
    )

    # Les identifiants en clair sont effacés du retained.
    assert no_real_mqtt.messages == [
        {
            "topic": f"growhub/v1/provision/{claimed_device.device_id}/creds",
            "payload": "",
            "retain": True,
        }
    ]


def test_confirmation_is_idempotent(claimed_device, no_real_mqtt):
    provisioning.provision_bootstrap(claimed_device)
    provisioning.provision_device(claimed_device)
    handle_message(f"growhub/v1/{claimed_device.device_id}/status", b"online")
    handle_message(
        f"growhub/v1/{claimed_device.device_id}/telemetry",
        {"sensors": {"ClimateSensor": {"temperature": 20}}},
    )
    no_real_mqtt.messages.clear()

    handle_message(
        f"growhub/v1/{claimed_device.device_id}/telemetry",
        {"sensors": {"ClimateSensor": {"temperature": 21}}},
    )
    assert no_real_mqtt.messages == []


def test_messages_without_credentials_are_untouched(device, no_real_mqtt):
    handle_message(
        f"growhub/v1/{device.device_id}/telemetry",
        {"sensors": {"ClimateSensor": {"temperature": 20}}},
    )
    assert MqttCredential.objects.count() == 0
    assert no_real_mqtt.messages == []


def test_revoke_credentials_cuts_the_device_off(claimed_device):
    provisioning.provision_device(claimed_device)
    credential = provisioning.revoke_credentials(claimed_device)

    assert credential.revoked_at is not None
    assert claimed_device.device_id not in BrokerFiles().read_users()


def test_revoke_is_safe_on_a_device_without_credentials(device):
    assert provisioning.revoke_credentials(device) is None
