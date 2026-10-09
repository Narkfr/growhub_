import pytest
from devices.models import Device, Membership
from devices.services import create_pairing_claim, redeem_pairing_code
from django.contrib.auth import get_user_model

User = get_user_model()


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
    claim, code = create_pairing_claim(device, code="ABC234")
    return device


@pytest.fixture
def claimed_device(pending_device, user):
    return redeem_pairing_code(user, "ABC234")
