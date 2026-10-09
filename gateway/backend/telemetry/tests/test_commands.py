import pytest
from devices.models import Membership
from django.utils import timezone
from telemetry.models import CommandAudit
from telemetry.services import CommandDispatchError, expire_pending_commands

pytestmark = pytest.mark.django_db


def test_owner_can_send_an_actuator_command(device, user, dispatcher, publisher):
    audit = dispatcher.send(device, user, "actuators", "ON", {"target": "WaterPump"})

    assert audit.status == CommandAudit.Status.SENT
    assert publisher.messages == [
        {
            "topic": "growhub/v1/ghb-3f2a91/cmd/actuators",
            "payload": {
                "cmd_id": str(audit.cmd_id),
                "action": "ON",
                "args": {"target": "WaterPump"},
            },
            "retain": False,
        }
    ]


def test_member_can_drive_actuators(device, other_user, dispatcher):
    device.add_member(other_user, role=Membership.Role.MEMBER)
    assert dispatcher.can_send(device, other_user, "actuators") is True
    assert dispatcher.can_send(device, other_user, "config") is False


def test_member_cannot_send_config(device, other_user, dispatcher):
    device.add_member(other_user, role=Membership.Role.MEMBER)
    with pytest.raises(PermissionError):
        dispatcher.send(device, other_user, "config", "SET_INTERVAL", {"seconds": 60})


def test_viewer_cannot_send_anything(device, other_user, dispatcher):
    device.add_member(other_user, role=Membership.Role.VIEWER)
    assert dispatcher.can_send(device, other_user, "actuators") is False
    assert dispatcher.can_send(device, other_user, "config") is False
    with pytest.raises(PermissionError):
        dispatcher.send(device, other_user, "actuators", "ON")


def test_stranger_cannot_send_anything(device, other_user, dispatcher):
    with pytest.raises(PermissionError):
        dispatcher.send(device, other_user, "actuators", "ON")


def test_unknown_kind_is_refused(device, user, dispatcher):
    with pytest.raises(CommandDispatchError):
        dispatcher.send(device, user, "lasers", "ON")


def test_broker_failure_is_audited(device, user, failing_publisher):
    from telemetry.services import CommandDispatcher

    failing = CommandDispatcher(publisher=failing_publisher)
    with pytest.raises(CommandDispatchError):
        failing.send(device, user, "actuators", "ON")

    audit = CommandAudit.objects.get()
    assert audit.status == CommandAudit.Status.FAILED
    assert "broker injoignable" in audit.error


def test_expire_pending_commands_flags_stale_ones(device, user, dispatcher):
    audit = dispatcher.send(device, user, "actuators", "ON")
    CommandAudit.objects.filter(pk=audit.pk).update(
        created_at=timezone.now() - timezone.timedelta(minutes=5)
    )

    assert expire_pending_commands(older_than_seconds=60) == 1
    audit.refresh_from_db()
    assert audit.status == CommandAudit.Status.TIMEOUT


def test_automatic_command_has_no_user(device, dispatcher):
    audit = dispatcher.send(device, None, "actuators", "ON")
    assert audit.user is None
