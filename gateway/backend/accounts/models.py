"""User model: Django's AbstractUser with a unique e-mail and a display name."""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """GrowHub account.

    ``username`` stays the login identifier (admin friendly); ``email`` is
    unique because account recovery and notifications rely on it.
    """

    email = models.EmailField("adresse e-mail", unique=True)
    display_name = models.CharField("nom affiché", max_length=80, blank=True)

    class Meta:
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"

    def __str__(self):
        return self.display_name or self.username

    @property
    def label(self):
        return self.display_name or self.username
