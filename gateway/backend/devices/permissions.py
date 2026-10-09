"""DRF permissions built on membership roles."""

from rest_framework import permissions

from .models import Membership


class DeviceAccessPermission(permissions.BasePermission):
    """Read for any member, write for the owner only."""

    message = "Vous n'avez pas accès à ce Bourgeon."

    def has_object_permission(self, request, view, obj):
        role = obj.role_of(request.user)
        if role is None:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return role == Membership.Role.OWNER


class IsSiteOwner(permissions.BasePermission):
    message = "Seul le propriétaire du site peut le modifier."

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return obj.owner_id == request.user.id
        return obj.owner_id == request.user.id
