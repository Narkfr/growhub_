from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        "username",
        "email",
        "display_name",
        "is_staff",
        "is_active",
        "date_joined",
    )
    search_fields = ("username", "email", "display_name")
    ordering = ("username",)
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("GrowHub", {"fields": ("display_name",)}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("GrowHub", {"fields": ("email", "display_name")}),
    )
