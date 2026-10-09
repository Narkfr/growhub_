"""Devices ("Bourgeons"), their owners and their broker credentials.

Ownership is data, never a topic: a device can change hands by editing a
``Membership`` row, and every query is scoped with ``Device.objects.for_user``.
"""

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

DEVICE_ID_VALIDATOR = RegexValidator(
    r"^ghb-[0-9a-f]{6}$",
    "Identifiant matériel invalide (format attendu : ghb-xxxxxx, hexadécimal).",
)


class DeviceQuerySet(models.QuerySet):
    """Queryset with the only safe entry point: ``for_user``."""

    def for_user(self, user):
        if user is None or not getattr(user, "is_authenticated", False):
            return self.none()
        return self.filter(memberships__user=user).distinct()

    def owned_by(self, user):
        return self.filter(memberships__user=user, memberships__role="owner")

    def active(self):
        return self.filter(status=Device.Status.PROVISIONED)


class Site(models.Model):
    """Optional grouping of devices (a greenhouse, a tunnel, a plot)."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sites"
    )
    name = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "name"], name="unique_site_name_per_owner"
            )
        ]
        verbose_name = "site"
        verbose_name_plural = "sites"

    def __str__(self):
        return self.name


class Device(models.Model):
    """A connected object: one Pico W board running the GrowHub firmware."""

    class Status(models.TextChoices):
        PENDING = "pending", "en attente d'appairage"
        PROVISIONED = "provisioned", "appairé"
        DISABLED = "disabled", "désactivé"

    device_id = models.CharField(
        max_length=32,
        unique=True,
        validators=[DEVICE_ID_VALIDATOR],
        help_text="Identité matérielle dérivée de machine.unique_id() (ghb-xxxxxx).",
    )
    slug = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=80)
    model = models.CharField(
        max_length=64, blank=True, help_text="Modèle matériel déclaré."
    )
    fw_version = models.CharField(max_length=32, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING
    )
    site = models.ForeignKey(
        Site, null=True, blank=True, on_delete=models.SET_NULL, related_name="devices"
    )
    last_seen = models.DateTimeField(null=True, blank=True)
    provisioned_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = DeviceQuerySet.as_manager()

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["status", "last_seen"]),
        ]
        verbose_name = "Bourgeon"
        verbose_name_plural = "Bourgeons"

    def __str__(self):
        return f"{self.name} ({self.device_id})"

    @property
    def is_online(self):
        if not self.last_seen:
            return False
        window = settings.GROWHUB["DEVICE_STALE_AFTER_SECONDS"]
        return (timezone.now() - self.last_seen).total_seconds() <= window

    def role_of(self, user):
        """Return the membership role of ``user`` on this device, or ``None``."""
        if user is None or not getattr(user, "is_authenticated", False):
            return None
        membership = self.memberships.filter(user=user).first()
        return membership.role if membership else None

    def add_member(self, user, role="member"):
        membership, _ = Membership.objects.get_or_create(
            device=self, user=user, defaults={"role": role}
        )
        return membership

    def transfer_to(self, user, demote_previous_owner=True):
        """Hand ownership over to ``user``.

        The outgoing owner is demoted to member (read access kept) so a
        handover never locks anyone out silently; remove them explicitly with
        the members endpoint if the device is being given away.
        """
        with transaction.atomic():
            previous = self.memberships.filter(role=Membership.Role.OWNER)
            if demote_previous_owner:
                previous.update(role=Membership.Role.MEMBER)
            else:
                previous.delete()
            membership, _ = Membership.objects.update_or_create(
                device=self, user=user, defaults={"role": Membership.Role.OWNER}
            )
            return membership


class Membership(models.Model):
    """Which user can see or control which device."""

    class Role(models.TextChoices):
        OWNER = "owner", "propriétaire"
        MEMBER = "member", "membre"

    device = models.ForeignKey(
        Device, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=8, choices=Role.choices, default=Role.MEMBER)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invitations_sent",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["device", "user"]
        constraints = [
            models.UniqueConstraint(
                fields=["device", "user"], name="unique_membership"
            ),
            models.UniqueConstraint(
                fields=["device"],
                condition=Q(role="owner"),
                name="unique_owner_per_device",
            ),
        ]
        verbose_name = "appartenance"
        verbose_name_plural = "appartenances"

    def __str__(self):
        return f"{self.user} · {self.device} · {self.get_role_display()}"


class Capability(models.Model):
    """A sensor or actuator declared by the device's ``info`` message."""

    class Kind(models.TextChoices):
        SENSOR = "sensor", "capteur"
        ACTUATOR = "actuator", "actionneur"

    device = models.ForeignKey(
        Device, on_delete=models.CASCADE, related_name="capabilities"
    )
    kind = models.CharField(max_length=8, choices=Kind.choices)
    name = models.CharField(
        max_length=64, help_text="Nom du composant, ex. ClimateSensor."
    )
    metrics = models.JSONField(
        default=list,
        blank=True,
        help_text="Métriques publiées par ce composant, ex. temperature, humidity.",
    )
    unit = models.CharField(max_length=16, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["device", "kind", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["device", "kind", "name"], name="unique_capability_per_device"
            )
        ]
        verbose_name = "capacité"
        verbose_name_plural = "capacités"

    def __str__(self):
        return f"{self.get_kind_display()} {self.name}"


class MqttCredential(models.Model):
    """Broker identity for one device.

    Only the broker side hash is kept: the clear-text password is generated,
    handed to the device once and never stored, so there is nothing to steal
    from the database.
    """

    device = models.OneToOneField(
        Device, on_delete=models.CASCADE, related_name="mqtt_credential"
    )
    username = models.CharField(max_length=64, unique=True)
    password_hash = models.CharField(
        max_length=255, help_text="Ligne de mot de passe Mosquitto."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "identifiant MQTT"
        verbose_name_plural = "identifiants MQTT"

    def __str__(self):
        return self.username

    @property
    def is_active(self):
        return self.revoked_at is None

    def revoke(self):
        self.revoked_at = timezone.now()
        self.save(update_fields=["revoked_at"])


class PairingClaim(models.Model):
    """One-shot claim code linking a freshly flashed device to its owner."""

    device = models.OneToOneField(
        Device, on_delete=models.CASCADE, related_name="pairing_claim"
    )
    code_hash = models.CharField(max_length=128)
    bootstrap_fingerprint = models.CharField(max_length=128, blank=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    claimed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="claims_redeemed",
    )
    claimed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "code d'appairage"
        verbose_name_plural = "codes d'appairage"

    def __str__(self):
        return f"claim {self.hardware_id}"

    @property
    def hardware_id(self):
        """Hardware id of the device being claimed (``device_id`` is the FK column)."""
        return self.device.device_id

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_claimed(self):
        return self.claimed_at is not None

    @property
    def is_locked(self):
        return self.attempts >= settings.GROWHUB["PAIRING_MAX_ATTEMPTS"]

    @property
    def is_redeemable(self):
        return not (self.is_claimed or self.is_expired or self.is_locked)
