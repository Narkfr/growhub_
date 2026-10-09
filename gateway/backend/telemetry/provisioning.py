"""Provisioning side of the pairing flow (stub completed at jalon M4).

The goal is to keep the ingest router complete today: a device that is not
paired yet publishes on ``growhub/v1/provision/<device_id>`` and we only record
that it is asking to be claimed. Credential delivery (Mosquitto user + ACL +
retained credentials message) lands with the M4 milestone.
"""

import logging

from devices.models import Device, PairingClaim
from django.utils import timezone

logger = logging.getLogger(__name__)


def record_provisioning_request(topic, payload):
    parts = topic.split("/")
    # growhub/v1/provision/<device_id>[/creds]
    device_id = parts[3] if len(parts) > 3 else ""
    if len(parts) >= 5 and parts[4] == "creds":
        # Credentials are published by us, never by a device.
        raise ValueError("un appareil ne publie pas sur son topic de credentials")

    device = Device.objects.filter(device_id=device_id).first()
    if device is None:
        logger.info("demande de provisioning d'un appareil inconnu: %s", device_id)
        return {"device_id": device_id, "known": False}

    claim = PairingClaim.objects.filter(device=device).first()
    if claim is None:
        logger.warning("appareil %s sans code d'appairage enregistré", device_id)
        return {"device_id": device_id, "known": True, "claim": False}

    info = payload if isinstance(payload, dict) else {}
    claim.bootstrap_fingerprint = claim.bootstrap_fingerprint or str(
        info.get("hw_id", "")
    )
    claim.save(update_fields=["bootstrap_fingerprint"])
    logger.info(
        "appareil %s en attente d'appairage (reçu %s)", device_id, timezone.now()
    )
    return {"device_id": device_id, "known": True, "claim": True}
