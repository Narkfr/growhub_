from django.contrib import admin

from .models import CommandAudit, Telemetry


@admin.register(CommandAudit)
class CommandAuditAdmin(admin.ModelAdmin):
    list_display = ("created_at", "device", "kind", "action", "status", "user")
    list_filter = ("kind", "status", "device")
    search_fields = ("device__device_id", "device__name", "action", "user__username")
    readonly_fields = ("cmd_id", "created_at", "acked_at")


@admin.register(Telemetry)
class TelemetryAdmin(admin.ModelAdmin):
    """Read-only: telemetry is machine written and never edited by hand."""

    list_display = ("ts", "device", "source", "metric", "value", "unit")
    list_filter = ("source", "metric")
    search_fields = ("device__device_id", "device__name", "metric")
    date_hierarchy = "ts"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
