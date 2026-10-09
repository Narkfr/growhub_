import pytest
from devices.models import Device, Membership, PairingClaim
from devices.services import (
    PairingError,
    create_pairing_claim,
    hash_pairing_code,
    normalize_pairing_code,
    redeem_pairing_code,
    register_failed_attempt,
)
from django.utils import timezone

pytestmark = pytest.mark.django_db


def test_normalize_code_accepts_user_typing():
    assert normalize_pairing_code(" abc-234 ") == "ABC234"
    assert normalize_pairing_code("abc234") == "ABC234"


def test_code_hash_is_salted_with_device_id(make_device):
    device = make_device(device_id="ghb-3f2a91")
    other = make_device(device_id="ghb-001122")
    assert hash_pairing_code("ABC234", device.device_id) != hash_pairing_code(
        "ABC234", other.device_id
    )


def test_create_claim_stores_hash_not_code(pending_device):
    claim = PairingClaim.objects.get(device=pending_device)
    assert claim.code_hash == hash_pairing_code("ABC234", pending_device.device_id)
    assert claim.code_hash != "ABC234"
    assert claim.is_redeemable is True


def test_redeem_attaches_owner_and_provisions(user, pending_device):
    device = redeem_pairing_code(user, "abc-234")

    assert device.status == Device.Status.PROVISIONED
    assert device.provisioned_at is not None
    assert device.role_of(user) == Membership.Role.OWNER
    claim = PairingClaim.objects.get(device=device)
    assert claim.claimed_by == user
    assert claim.claimed_at is not None
    assert claim.is_redeemable is False


def test_redeem_twice_is_refused(user, other_user, pending_device):
    redeem_pairing_code(user, "ABC234")
    with pytest.raises(PairingError) as excinfo:
        redeem_pairing_code(other_user, "ABC234")
    assert excinfo.value.code == "already_claimed"


def test_redeem_with_unknown_code(user, pending_device):
    with pytest.raises(PairingError) as excinfo:
        redeem_pairing_code(user, "ZZZZZZ")
    assert excinfo.value.code == "unknown"


def test_redeem_with_malformed_code(user):
    with pytest.raises(PairingError) as excinfo:
        redeem_pairing_code(user, "AB")
    assert excinfo.value.code == "malformed"


def test_expired_claim_is_refused(user, pending_device):
    PairingClaim.objects.filter(device=pending_device).update(
        expires_at=timezone.now() - timezone.timedelta(minutes=1)
    )
    with pytest.raises(PairingError) as excinfo:
        redeem_pairing_code(user, "ABC234")
    assert excinfo.value.code == "expired"


def test_attempts_lock_the_claim(user, pending_device, settings):
    for _ in range(settings.GROWHUB["PAIRING_MAX_ATTEMPTS"]):
        assert register_failed_attempt("ABC234") is True

    claim = PairingClaim.objects.get(device=pending_device)
    assert claim.is_locked is True
    with pytest.raises(PairingError) as excinfo:
        redeem_pairing_code(user, "ABC234")
    assert excinfo.value.code == "locked"


def test_failed_attempt_on_unknown_code_is_ignored(pending_device):
    assert register_failed_attempt("ZZZZZZ") is False
    assert PairingClaim.objects.get(device=pending_device).attempts == 0


def test_create_pairing_claim_is_idempotent(pending_device):
    claim, code = create_pairing_claim(pending_device, code="XYZ789")
    assert claim.hardware_id == pending_device.device_id
    assert PairingClaim.objects.count() == 1
    assert claim.code_hash == hash_pairing_code("XYZ789", pending_device.device_id)
    assert code == "XYZ789"
