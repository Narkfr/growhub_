from django.contrib import admin

from .models import Capability, Device, Membership, MqttCredential, PairingClaim, Site


class CapabilityInline(admin.TabularInline):
    model = Capability
    extra = 0


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ("user",)


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "created_at")
    search_fields = ("name", "owner__username", "owner__email")
    list_select_related = ("owner",)


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = (
        "device_id",
        "name",
        "status",
        "owner",
        "site",
        "is_online",
        "last_seen",
    )
    list_filter = ("status", "site")
    search_fields = ("device_id", "name", "slug", "model")
    readonly_fields = ("created_at", "updated_at", "last_seen", "provisioned_at")
    inlines = (CapabilityInline, MembershipInline)
    list_select_related = ("site",)

    @admin.display(description="propriétaire")
    def owner(self, obj):
        membership = obj.memberships.filter(role=Membership.Role.OWNER).first()
        return membership.user if membership else "—"


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("device", "user", "role", "created_at")
    list_filter = ("role",)
    autocomplete_fields = ("user", "device")
    search_fields = ("device__name", "device__device_id", "user__username")


@admin.register(MqttCredential)
class MqttCredentialAdmin(admin.ModelAdmin):
    list_display = ("username", "device", "created_at", "revoked_at", "last_used_at")
    search_fields = ("username", "device__device_id")
    readonly_fields = ("password_hash", "created_at", "last_used_at")


@admin.register(PairingClaim)
class PairingClaimAdmin(admin.ModelAdmin):
    list_display = ("device", "expires_at", "attempts", "claimed_by", "claimed_at")
    list_filter = ("claimed_by",)
    readonly_fields = ("code_hash", "created_at", "claimed_at", "attempts")
    search_fields = ("device__device_id", "device__name")


@admin.register(Capability)
class CapabilityAdmin(admin.ModelAdmin):
    list_display = ("device", "kind", "name", "metrics", "active")
    list_filter = ("kind", "active")
    search_fields = ("name", "device__device_id")
