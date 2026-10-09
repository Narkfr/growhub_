"""Domain services: pairing redemption and capability synchronisation."""

import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Capability, Device, Membership, PairingClaim

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6


class PairingError(Exception):
    """Raised when a claim code cannot be redeemed."""

    def __init__(self, message, code="invalid"):
        super().__init__(message)
        self.code = code


def generate_pairing_code():
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def normalize_pairing_code(raw):
    cleaned = "".join(ch for ch in str(raw).upper() if ch.isalnum())
    return cleaned


def hash_pairing_code(code, device_id, pepper=""):
    """Per-device salt: a leaked hash is useless for another device."""
    payload = f"{device_id}:{normalize_pairing_code(code)}:{pepper}".encode()
    return hashlib.sha256(payload).hexdigest()


def create_pairing_claim(device, code=None, ttl_hours=None, bootstrap_fingerprint=""):
    """Register (or refresh) the claim of a device awaiting pairing."""
    code = normalize_pairing_code(code) if code else generate_pairing_code()
    ttl = ttl_hours or settings.GROWHUB["PAIRING_CODE_TTL_HOURS"]
    claim, _ = PairingClaim.objects.update_or_create(
        device=device,
        defaults={
            "code_hash": hash_pairing_code(code, device.device_id),
            "bootstrap_fingerprint": bootstrap_fingerprint,
            "expires_at": timezone.now() + timedelta(hours=ttl),
            "attempts": 0,
            "claimed_by": None,
            "claimed_at": None,
        },
    )
    return claim, code


def redeem_pairing_code(user, raw_code):
    """Attach a device to ``user`` as owner, consuming its claim code.

    The hash is salted with the device id, so the lookup walks the pending
    claims instead of querying by hash. Pending claims are few by construction
    (a device is claimed once, right after flashing).
    """
    code = normalize_pairing_code(raw_code)
    if len(code) != CODE_LENGTH:
        raise PairingError("Code d'appairage invalide.", code="malformed")

    def find(queryset):
        for candidate in queryset.select_related("device").order_by("created_at"):
            expected = hash_pairing_code(code, candidate.device.device_id)
            if hmac.compare_digest(expected, candidate.code_hash):
                return candidate
        return None

    # Common path: still-open claims. Only if nothing matches do we look at
    # already-claimed ones, to answer "already used" instead of "unknown".
    match = find(PairingClaim.objects.filter(claimed_at__isnull=True))
    if match is None:
        if find(PairingClaim.objects.exclude(claimed_at__isnull=True)) is not None:
            raise PairingError("Ce code a déjà été utilisé.", code="already_claimed")
        raise PairingError("Code d'appairage inconnu.", code="unknown")

    if match.is_locked:
        raise PairingError("Trop de tentatives, code verrouillé.", code="locked")
    if match.is_expired:
        raise PairingError("Code expiré, refaites un appairage.", code="expired")

    with transaction.atomic():
        match.claimed_by = user
        match.claimed_at = timezone.now()
        match.save(update_fields=["claimed_by", "claimed_at"])

        device = match.device
        device.status = Device.Status.PROVISIONED
        device.provisioned_at = device.provisioned_at or timezone.now()
        device.save(update_fields=["status", "provisioned_at"])
        device.add_member(user, role=Membership.Role.OWNER)
    return device


def register_failed_attempt(raw_code):
    """Count a failed redemption on the matching claim, if any."""

    code = normalize_pairing_code(raw_code)
    for claim in PairingClaim.objects.filter(claimed_at__isnull=True):
        expected = hash_pairing_code(code, claim.device.device_id)
        if hmac.compare_digest(expected, claim.code_hash):
            PairingClaim.objects.filter(pk=claim.pk).update(attempts=claim.attempts + 1)
            return True
    return False


def sync_capabilities(device, info_payload):
    """Create/update capabilities from a device ``info`` message.

    Expected shape::

        {"model": "Bourgeon V1", "fw": "2.0.0",
         "sensors": [{"name": "ClimateSensor", "metrics": ["temperature"]}],
         "actuators": [{"name": "WaterPump"}]}
    """
    created = []
    for kind, key in (
        (Capability.Kind.SENSOR, "sensors"),
        (Capability.Kind.ACTUATOR, "actuators"),
    ):
        for entry in info_payload.get(key, []) or []:
            if isinstance(entry, str):
                entry = {"name": entry}
            name = entry.get("name")
            if not name:
                continue
            capability, _ = Capability.objects.update_or_create(
                device=device,
                kind=kind,
                name=name,
                defaults={
                    "metrics": entry.get("metrics", []),
                    "unit": entry.get("unit", ""),
                    "active": True,
                },
            )
            created.append(capability)

    update_fields = []
    if info_payload.get("model"):
        device.model = info_payload["model"]
        update_fields.append("model")
    if info_payload.get("fw"):
        device.fw_version = info_payload["fw"]
        update_fields.append("fw_version")
    if update_fields:
        device.save(update_fields=update_fields)
    return created
