"""Staff-only provisioning endpoints."""

import pytest
from devices.models import Device, MqttCredential
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff_client(user):
    staff = user.__class__.objects.create_superuser(
        username="admin", email="admin@example.com", password="motdepasse-long-3"
    )
    client = APIClient()
    client.force_authenticate(user=staff)
    return client


@pytest.fixture
def user_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_provisioning_requires_staff(user_client, claimed_device):
    response = user_client.post(f"/api/v1/devices/{claimed_device.id}/provision")
    assert response.status_code == 403
    assert MqttCredential.objects.count() == 0


def test_provisioning_returns_the_password_once(staff_client, claimed_device):
    response = staff_client.post(f"/api/v1/devices/{claimed_device.id}/provision")
    assert response.status_code == 201
    body = response.json()
    assert body["username"] == claimed_device.device_id
    assert len(body["password"]) >= 24
    assert body["topic"] == f"growhub/v1/provision/{claimed_device.device_id}/creds"

    # La base ne garde que l'empreinte.
    credential = MqttCredential.objects.get(device=claimed_device)
    assert body["password"] not in credential.password_hash

    # Rejouer l'appel régénère un mot de passe côté fichier broker.
    second = staff_client.post(f"/api/v1/devices/{claimed_device.id}/provision")
    assert second.status_code == 201
    assert second.json()["password"] != body["password"]


def test_provisioning_refuses_an_unpaired_device(staff_client, pending_device):
    response = staff_client.post(f"/api/v1/devices/{pending_device.id}/provision")
    assert response.status_code == 400
    assert Device.objects.get(pk=pending_device.pk).status == Device.Status.PENDING


def test_revoke_endpoint_requires_staff(user_client, staff_client, claimed_device):
    assert (
        user_client.post(
            f"/api/v1/devices/{claimed_device.id}/provision/revoke"
        ).status_code
        == 403
    )

    response = staff_client.post(
        f"/api/v1/devices/{claimed_device.id}/provision/revoke"
    )
    assert response.status_code == 200
    assert response.json()["revoked_at"] is None  # aucun identifiant n'existait
