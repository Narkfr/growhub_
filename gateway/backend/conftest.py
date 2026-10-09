import pytest
from devices.models import Device, Membership
from devices.services import create_pairing_claim, redeem_pairing_code
from django.contrib.auth import get_user_model
from telemetry.services import CommandDispatcher

User = get_user_model()


@pytest.fixture(autouse=True)
def isolated_broker_dir(tmp_path, settings):
    """Never let a test touch gateway/mosquitto/config.

    Every test gets its own broker config directory and no reload command.
    """
    settings.GROWHUB = {
        **settings.GROWHUB,
        "MOSQUITTO_CONFIG_DIR": str(tmp_path / "mosquitto"),
        "MQTT_RELOAD_COMMAND": "",
    }
    return tmp_path / "mosquitto"


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="marius", email="marius@example.com", password="motdepasse-long-1"
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        username="camille", email="camille@example.com", password="motdepasse-long-2"
    )


@pytest.fixture
def make_device(db):
    def factory(device_id="ghb-3f2a91", name="Bourgeon serre 1", owner=None, **kwargs):
        device = Device.objects.create(
            device_id=device_id,
            slug=device_id,
            name=name,
            model=kwargs.pop("model", "Bourgeon V1"),
            status=kwargs.pop("status", Device.Status.PROVISIONED),
            **kwargs,
        )
        if owner is not None:
            device.add_member(owner, role=Membership.Role.OWNER)
        return device

    return factory


@pytest.fixture
def device(make_device, user):
    return make_device(owner=user)


@pytest.fixture
def pending_device(make_device):
    """A flashed device with an open claim code ``ABC234``."""
    device = make_device(device_id="ghb-7c1d02", status=Device.Status.PENDING)
    create_pairing_claim(device, code="ABC234")
    return device


@pytest.fixture
def claimed_device(pending_device, user):
    return redeem_pairing_code(user, "ABC234")


class FakePublisher:
    """Records published messages instead of talking to a broker."""

    def __init__(self, fail_with=None):
        self.messages = []
        self.fail_with = fail_with

    def publish(self, topic, payload, retain=False, qos=0):
        if self.fail_with is not None:
            raise self.fail_with
        self.messages.append({"topic": topic, "payload": payload, "retain": retain})
        return len(self.messages)

    def close(self):
        pass


@pytest.fixture
def publisher():
    return FakePublisher()


@pytest.fixture
def failing_publisher():
    """Exploitable par les tests qui vérifient l'audit d'un broker injoignable."""
    return FakePublisher(fail_with=OSError("broker injoignable"))


@pytest.fixture(autouse=True)
def no_real_mqtt(monkeypatch, publisher):
    """No test ever opens a socket to a broker: every publisher is the fake one."""
    monkeypatch.setattr("telemetry.mqtt.MqttPublisher", lambda **kwargs: publisher)
    return publisher


@pytest.fixture
def dispatcher(publisher):
    return CommandDispatcher(publisher=publisher)
