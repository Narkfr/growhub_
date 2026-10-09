"""Time series storage and the audit trail of every command sent."""

from devices.models import Device
from django.conf import settings
from django.db import models
from django.utils import timezone


class Telemetry(models.Model):
    """One metric of one device at one instant.

    Rows are written by the MQTT worker in bulk; the ``(device, ts)`` index
    serves both the dashboard history and the retention purge.
    """

    device = models.ForeignKey(
        Device, on_delete=models.CASCADE, related_name="telemetry"
    )
    ts = models.DateTimeField(db_index=True)
    source = models.CharField(max_length=64, help_text="Composant, ex. ClimateSensor.")
    metric = models.CharField(max_length=64, help_text="Métrique, ex. temperature.")
    value = models.FloatField(null=True)
    unit = models.CharField(max_length=16, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-ts"]
        indexes = [
            models.Index(fields=["device", "-ts"], name="telemetry_device_ts_idx"),
            models.Index(
                fields=["device", "metric", "-ts"], name="telemetry_metric_ts_idx"
            ),
        ]
        verbose_name = "mesure"
        verbose_name_plural = "mesures"

    def __str__(self):
        return f"{self.device_id} · {self.metric}={self.value}{self.unit}"

    @property
    def device_id(self):
        return self.device.device_id


class CommandAudit(models.Model):
    """Who asked which device to do what, and what came back."""

    class Status(models.TextChoices):
        SENT = "sent", "envoyée"
        ACKED = "acked", "confirmée"
        FAILED = "failed", "en échec"
        TIMEOUT = "timeout", "sans réponse"

    device = models.ForeignKey(
        Device, on_delete=models.CASCADE, related_name="commands"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="commands_sent",
        help_text="Vide pour une commande automatique (moteur ITK).",
    )
    cmd_id = models.UUIDField(unique=True)
    kind = models.CharField(max_length=16, help_text="actuators, sensors ou config.")
    action = models.CharField(max_length=32)
    args = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.SENT)
    error = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    acked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["device", "-created_at"], name="command_device_created_idx"
            )
        ]
        verbose_name = "commande"
        verbose_name_plural = "commandes"

    def __str__(self):
        return f"{self.device_id} {self.kind}:{self.action} ({self.status})"

    @property
    def device_id(self):
        return self.device.device_id

    def mark_acked(self, ok, error="", state=None):
        self.status = self.Status.ACKED if ok else self.Status.FAILED
        self.error = (error or "")[:255]
        self.acked_at = timezone.now()
        self.save(update_fields=["status", "error", "acked_at"])
