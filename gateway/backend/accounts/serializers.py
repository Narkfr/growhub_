from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    label = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ("id", "username", "email", "display_name", "label", "is_staff")
        read_only_fields = ("id", "username", "is_staff")
