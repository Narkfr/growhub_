"""Pairing, step two: hand real MQTT credentials to a freshly flashed device.

Flow (see docs/pairing.md):

1. the provisioning tool creates the device, its claim code and a temporary
   bootstrap broker account (``boot-<device_id>``);
2. the device boots, publishes on ``growhub/v1/provision/<device_id>`` and shows
   the code on its screen;
3. the owner redeems the code in the app (``devices.services.redeem_pairing_code``);
4. this module then creates the real account (``username == device_id``), writes
   the broker password/ACL files, reloads the broker and publishes the
   credentials retained on ``.../provision/<device_id>/creds``;
5. the first message the device sends with those credentials confirms the
   handover: the retained message is cleared and the bootstrap account removed.

Messages from unknown or unpaired devices land here too: a device that is not
paired yet only announces itself, it never writes data.
"""

import logging

from devices.models import Device, MqttCredential, PairingClaim
from django.conf import settings
from django.utils import timezone
from growhub import topics

from .mosquitto import BrokerFiles, bootstrap_username

logger = logging.getLogger(__name__)


class ProvisioningError(Exception):
    """Raised when credentials cannot be handed over."""


def default_publisher():
    from .mqtt import MqttPublisher

    return MqttPublisher(client_id="growhub-backend-prov")


def devices_awaiting_pairing():
    """Device ids with an *open* pairing claim: they need bootstrap ACL entries.

    Queried from PairingClaim, not from Device: filtering a reverse OneToOne
    with ``isnull=True`` also matches devices that have no claim row at all.
    """
    return list(
        PairingClaim.objects.filter(claimed_at__isnull=True).values_list(
            "device__device_id", flat=True
        )
    )


def refresh_broker_acl(broker=None):
    broker = broker or BrokerFiles()
    broker.write_acl(devices_awaiting_pairing())
    broker.reload()
    return broker


def provision_bootstrap(device, password=None, broker=None):
    """Create (or reset) the temporary broker account used before pairing."""
    broker = broker or BrokerFiles()
    username = bootstrap_username(device.device_id)
    password, _ = broker.set_password(username, password)
    refresh_broker_acl(broker)
    return username, password


def provision_device(device, broker=None, publisher=None, password=None):
    """Create the device's own broker account and push the credentials to it.

    Returns ``(credential, password)``. The clear-text password exists only
    here, in the broker's file and in the retained MQTT message: the database
    keeps the hash alone.
    """
    broker = broker or BrokerFiles()
    publisher = publisher or default_publisher()

    if device.status != Device.Status.PROVISIONED:
        raise ProvisioningError(
            "L'appareil doit d'abord être appairé (code de réclamation)."
        )

    password, password_hash = broker.set_password(device.device_id, password)
    credential, _ = MqttCredential.objects.update_or_create(
        device=device,
        defaults={
            "username": device.device_id,
            "password_hash": password_hash,
            "revoked_at": None,
            "installed_at": None,
        },
    )
    refresh_broker_acl(broker)

    payload = {
        "username": device.device_id,
        "password": password,
        "broker": settings.MQTT_BROKER,
        "port": settings.MQTT_PORT,
    }
    publisher.publish(
        topics.provision_credentials_topic(device.device_id), payload, retain=True
    )
    logger.info("identifiants MQTT générés et publiés pour %s", device.device_id)
    return credential, password


def maybe_confirm_credentials(device, broker=None, publisher=None):
    """Called on every device message: finish the handover on the first one.

    Cheap on the hot path: returns immediately when the device has no pending
    credentials. When it does, the device has proven it read the retained
    message, so we clear it and remove the bootstrap account.
    """
    credential = MqttCredential.objects.filter(
        device=device, installed_at__isnull=True
    ).first()
    if credential is None or credential.revoked_at is not None:
        return None
    return confirm_credentials(device, credential, broker=broker, publisher=publisher)


def confirm_credentials(device, credential=None, broker=None, publisher=None):
    credential = credential or getattr(device, "mqtt_credential", None)
    if credential is None or credential.installed_at is not None:
        return None

    broker = broker or BrokerFiles()
    publisher = publisher or default_publisher()

    credential.installed_at = timezone.now()
    credential.save(update_fields=["installed_at"])

    # The device runs on its own account now: drop the temporary one.
    if broker.remove_user(bootstrap_username(device.device_id)):
        credential.bootstrap_revoked_at = timezone.now()
        credential.save(update_fields=["bootstrap_revoked_at"])
    refresh_broker_acl(broker)

    # Clear the retained credentials so they are not replayed to anyone.
    publisher.publish(
        topics.provision_credentials_topic(device.device_id), "", retain=True
    )
    logger.info(
        "appairage terminé pour %s, compte d'amorçage révoqué", device.device_id
    )
    return credential


def revoke_credentials(device, broker=None):
    """Cut a device off the broker (lost, stolen, replaced)."""
    credential = getattr(device, "mqtt_credential", None)
    broker = broker or BrokerFiles()
    if credential is not None and credential.revoked_at is None:
        credential.revoked_at = timezone.now()
        credential.save(update_fields=["revoked_at"])
    broker.remove_user(device.device_id)
    refresh_broker_acl(broker)
    return credential


def register_claim(device, code=None, ttl_hours=None, bootstrap_fingerprint=""):
    """Thin re-export so tools and the management command read one module."""
    from devices.services import create_pairing_claim

    return create_pairing_claim(
        device,
        code=code,
        ttl_hours=ttl_hours,
        bootstrap_fingerprint=bootstrap_fingerprint,
    )


def open_claims():
    return PairingClaim.objects.filter(claimed_at__isnull=True).select_related("device")


def record_provisioning_request(topic, payload):
    """Bootstrap message from a device that is not paired yet.

    Returns a small dict so the ingest router (and its tests) can assert what
    happened; nothing is written to the device rows here.
    """
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
    logger.info("appareil %s en attente d'appairage", device_id)
    return {"device_id": device_id, "known": True, "claim": True}
