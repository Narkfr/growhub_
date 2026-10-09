"""Validation of the payloads published by devices."""

from rest_framework import serializers

from .models import CommandAudit, Telemetry


class MetricSerializer(serializers.Serializer):
    value = serializers.FloatField(required=False, allow_null=True)
    unit = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class TelemetryPayloadSerializer(serializers.Serializer):
    """Payload of ``growhub/v1/<device_id>/telemetry``.

    Sensors may be published either as ``{"value": 42, "unit": "percent"}`` or
    as a bare number; both shapes are accepted, ``None`` means the read failed.
    """

    ts = serializers.DateTimeField(required=False)
    seq = serializers.IntegerField(required=False, allow_null=True)
    sensors = serializers.DictField(child=serializers.DictField(), required=False)
    actuators = serializers.DictField(required=False)

    def validate_sensors(self, value):
        cleaned = {}
        for component, metrics in value.items():
            if not isinstance(metrics, dict):
                raise serializers.ValidationError(
                    f"{component} doit être un objet de métriques."
                )
            cleaned[component] = metrics
        return cleaned


class InfoPayloadSerializer(serializers.Serializer):
    model = serializers.CharField(required=False, allow_blank=True)
    fw = serializers.CharField(required=False, allow_blank=True)
    hw_id = serializers.CharField(required=False, allow_blank=True)
    sensors = serializers.ListField(required=False)
    actuators = serializers.ListField(required=False)


class AckPayloadSerializer(serializers.Serializer):
    cmd_id = serializers.UUIDField()
    ok = serializers.BooleanField(default=True)
    error = serializers.CharField(required=False, allow_blank=True)
    state = serializers.DictField(required=False)


class CommandRequestSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=("actuators", "sensors", "config"))
    action = serializers.CharField(max_length=32)
    args = serializers.DictField(required=False)


class CommandAuditSerializer(serializers.ModelSerializer):
    device_id = serializers.CharField(read_only=True)
    user_label = serializers.CharField(
        source="user.label", read_only=True, default=None
    )

    class Meta:
        model = CommandAudit
        fields = (
            "id",
            "cmd_id",
            "device_id",
            "device",
            "user",
            "user_label",
            "kind",
            "action",
            "args",
            "status",
            "error",
            "created_at",
            "acked_at",
        )
        read_only_fields = fields


class TelemetrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Telemetry
        fields = ("id", "device", "ts", "source", "metric", "value", "unit")
        read_only_fields = fields
