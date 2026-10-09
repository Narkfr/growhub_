import pytest
from devices.models import Capability, Device, Membership
from devices.services import sync_capabilities
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

pytestmark = pytest.mark.django_db


def test_device_id_must_match_hardware_pattern(make_device):
    device = make_device(device_id="ghb-3f2a91")
    device.full_clean()

    device.device_id = "serre-du-fond"
    with pytest.raises(ValidationError):
        device.full_clean()


def test_owner_is_unique_per_device(device, other_user):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            device.add_member(other_user, role=Membership.Role.OWNER)


def test_membership_is_unique(device, other_user):
    device.add_member(other_user, role=Membership.Role.MEMBER)
    # add_member is idempotent...
    assert device.add_member(other_user, role=Membership.Role.MEMBER).pk is not None
    assert device.memberships.filter(user=other_user).count() == 1
    # ...and the database refuses a duplicate row anyway.
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Membership.objects.create(
                device=device, user=other_user, role=Membership.Role.MEMBER
            )


def test_for_user_scopes_devices(device, other_user, make_device):
    stranger_view = Device.objects.for_user(other_user)
    assert list(stranger_view) == []

    make_device(device_id="ghb-001122", owner=other_user)
    assert [d.device_id for d in Device.objects.for_user(other_user)] == ["ghb-001122"]
    assert [
        d.device_id for d in Device.objects.for_user(device.memberships.first().user)
    ] == ["ghb-3f2a91"]


def test_for_user_ignores_anonymous():
    from django.contrib.auth.models import AnonymousUser

    assert list(Device.objects.for_user(AnonymousUser())) == []


def test_role_of(device, user, other_user):
    assert device.role_of(user) == Membership.Role.OWNER
    assert device.role_of(other_user) is None
    device.add_member(other_user, role=Membership.Role.MEMBER)
    assert device.role_of(other_user) == Membership.Role.MEMBER


def test_is_online_tracks_last_seen(device):
    assert device.is_online is False
    device.last_seen = timezone.now()
    device.save(update_fields=["last_seen"])
    assert device.is_online is True

    device.last_seen = timezone.now() - timezone.timedelta(hours=2)
    device.save(update_fields=["last_seen"])
    assert device.is_online is False


def test_transfer_demotes_the_outgoing_owner_to_read_only(device, user, other_user):
    device.transfer_to(other_user)

    roles = {m.user_id: m.role for m in device.memberships.all()}
    assert roles[other_user.id] == Membership.Role.OWNER
    assert roles[user.id] == Membership.Role.VIEWER
    assert device.memberships.filter(role=Membership.Role.OWNER).count() == 1


def test_clean_handover_removes_the_outgoing_owner(device, user, other_user):
    device.transfer_to(other_user, keep_access=False)

    assert not device.memberships.filter(user=user).exists()
    assert device.role_of(other_user) == Membership.Role.OWNER


def test_transfer_promotes_existing_member(device, user, other_user):
    device.add_member(other_user, role=Membership.Role.MEMBER)
    device.transfer_to(other_user)

    assert device.memberships.filter(user=other_user).count() == 1
    assert device.role_of(other_user) == Membership.Role.OWNER
    assert device.role_of(user) == Membership.Role.VIEWER


def test_sync_capabilities_from_info_message(device):
    payload = {
        "model": "Bourgeon V1",
        "fw": "2.0.0",
        "sensors": [{"name": "ClimateSensor", "metrics": ["temperature", "humidity"]}],
        "actuators": [{"name": "WaterPump"}],
    }
    capabilities = sync_capabilities(device, payload)

    assert len(capabilities) == 2
    device.refresh_from_db()
    assert device.fw_version == "2.0.0"
    assert set(device.capabilities.values_list("name", flat=True)) == {
        "ClimateSensor",
        "WaterPump",
    }
    assert device.capabilities.get(kind=Capability.Kind.SENSOR).metrics == [
        "temperature",
        "humidity",
    ]

    # A second info message updates in place instead of duplicating.
    sync_capabilities(device, {"sensors": [{"name": "ClimateSensor"}]})
    assert device.capabilities.filter(name="ClimateSensor").count() == 1
