from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Capability, Device, Membership, MqttCredential, Site

User = get_user_model()


class CapabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Capability
        fields = ("id", "kind", "name", "metrics", "unit", "active")
        read_only_fields = fields


class MembershipSerializer(serializers.ModelSerializer):
    user_label = serializers.CharField(source="user.label", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Membership
        fields = ("id", "user", "username", "user_label", "role", "created_at")
        read_only_fields = ("id", "user", "username", "user_label", "created_at")


class SiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = ("id", "name", "description", "created_at")
        read_only_fields = ("id", "created_at")


class DeviceSerializer(serializers.ModelSerializer):
    capabilities = CapabilitySerializer(many=True, read_only=True)
    memberships = MembershipSerializer(many=True, read_only=True)
    site_name = serializers.CharField(source="site.name", read_only=True, default=None)
    is_online = serializers.BooleanField(read_only=True)
    role = serializers.SerializerMethodField()

    class Meta:
        model = Device
        fields = (
            "id",
            "device_id",
            "slug",
            "name",
            "model",
            "fw_version",
            "status",
            "site",
            "site_name",
            "last_seen",
            "provisioned_at",
            "is_online",
            "role",
            "capabilities",
            "memberships",
            "created_at",
        )
        read_only_fields = (
            "id",
            "device_id",
            "slug",
            "model",
            "fw_version",
            "status",
            "last_seen",
            "provisioned_at",
            "created_at",
        )

    def get_role(self, obj):
        request = self.context.get("request")
        if request is None:
            return None
        return obj.role_of(request.user)


class MembershipWriteSerializer(serializers.Serializer):
    username = serializers.CharField()
    role = serializers.ChoiceField(
        choices=Membership.Role.choices, default=Membership.Role.MEMBER
    )

    def validate_username(self, value):
        try:
            return User.objects.get(username=value)
        except User.DoesNotExist as exc:
            raise serializers.ValidationError("Aucun utilisateur avec ce nom.") from exc


class TransferSerializer(serializers.Serializer):
    """Ownership handover payload.

    ``keep_access`` (default true) keeps the outgoing owner as a read-only
    viewer; false removes them from the device.
    """

    username = serializers.CharField()

    keep_access = serializers.BooleanField(default=True)

    def validate_username(self, value):
        try:
            return User.objects.get(username=value)
        except User.DoesNotExist as exc:
            raise serializers.ValidationError("Aucun utilisateur avec ce nom.") from exc


class PairingClaimCreateSerializer(serializers.Serializer):
    """Used by the provisioning tool (staff only)."""

    device_id = serializers.RegexField(r"^ghb-[0-9a-f]{6}$")
    code = serializers.CharField(max_length=12, required=False, allow_blank=True)
    name = serializers.CharField(max_length=80, required=False, allow_blank=True)
    model = serializers.CharField(max_length=64, required=False, allow_blank=True)
    ttl_hours = serializers.IntegerField(required=False, min_value=1, max_value=720)
    bootstrap_fingerprint = serializers.CharField(
        max_length=128, required=False, allow_blank=True
    )

    def validate_device_id(self, value):
        if Device.objects.filter(device_id=value).exists():
            raise serializers.ValidationError("Cet appareil existe déjà.")
        return value


class PairingRedeemSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=12)


class DeviceInfoSerializer(serializers.Serializer):
    """Payload published by a device on its ``info`` topic (used by tests and tools)."""

    model = serializers.CharField(required=False, allow_blank=True)
    fw = serializers.CharField(required=False, allow_blank=True)
    sensors = serializers.ListField(child=serializers.DictField(), required=False)
    actuators = serializers.ListField(child=serializers.DictField(), required=False)


class MqttCredentialSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = MqttCredential
        fields = (
            "id",
            "username",
            "created_at",
            "revoked_at",
            "last_used_at",
            "is_active",
        )
        read_only_fields = fields
