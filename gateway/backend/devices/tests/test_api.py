import pytest
from devices.models import Device, Membership, PairingClaim
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def auth_client(client, user):
    client.force_authenticate(user=user)
    return client


def test_login_logout_and_me(client, user):
    response = client.post(
        "/api/v1/auth/login",
        {"username": "marius", "password": "motdepasse-long-1"},
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["username"] == "marius"

    assert client.get("/api/v1/auth/me").status_code == 200
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me").status_code in (401, 403)


def test_login_refuses_bad_password(client, user):
    response = client.post(
        "/api/v1/auth/login", {"username": "marius", "password": "faux"}, format="json"
    )
    assert response.status_code == 401


def test_devices_require_authentication(client):
    assert client.get("/api/v1/devices").status_code in (401, 403)


def test_device_list_is_scoped_to_memberships(
    auth_client, device, other_user, make_device
):
    make_device(device_id="ghb-001122", name="Chez Camille", owner=other_user)

    payload = auth_client.get("/api/v1/devices").json()
    assert payload["count"] == 1
    assert payload["results"][0]["device_id"] == "ghb-3f2a91"
    assert payload["results"][0]["role"] == "owner"


def test_device_detail_from_stranger_is_not_found(auth_client, other_user, make_device):
    stranger_device = make_device(device_id="ghb-001122", owner=other_user)
    assert auth_client.get(f"/api/v1/devices/{stranger_device.id}").status_code == 404


def test_member_can_read_but_not_rename(auth_client, device, other_user):
    device.add_member(other_user, role=Membership.Role.MEMBER)

    member_client = APIClient()
    member_client.force_authenticate(user=other_user)
    assert member_client.get(f"/api/v1/devices/{device.id}").status_code == 200
    assert (
        member_client.patch(
            f"/api/v1/devices/{device.id}", {"name": "Piraté"}, format="json"
        ).status_code
        == 403
    )


def test_owner_can_rename(auth_client, device):
    response = auth_client.patch(
        f"/api/v1/devices/{device.id}", {"name": "Serre tomates"}, format="json"
    )
    assert response.status_code == 200
    device.refresh_from_db()
    assert device.name == "Serre tomates"


def test_owner_manages_members(auth_client, device, other_user):
    created = auth_client.post(
        f"/api/v1/devices/{device.id}/members",
        {"username": "camille", "role": "member"},
        format="json",
    )
    assert created.status_code == 201
    assert device.memberships.filter(user=other_user).count() == 1

    # Duplicate membership is refused.
    assert (
        auth_client.post(
            f"/api/v1/devices/{device.id}/members",
            {"username": "camille"},
            format="json",
        ).status_code
        == 400
    )

    removed = auth_client.delete(f"/api/v1/devices/{device.id}/members/{other_user.id}")
    assert removed.status_code == 204
    assert device.memberships.filter(user=other_user).count() == 0


def test_owner_cannot_remove_itself(auth_client, device, user):
    response = auth_client.delete(f"/api/v1/devices/{device.id}/members/{user.id}")
    assert response.status_code == 400


def test_member_cannot_add_members(device, other_user, user):
    device.add_member(other_user, role=Membership.Role.MEMBER)
    member_client = APIClient()
    member_client.force_authenticate(user=other_user)

    response = member_client.post(
        f"/api/v1/devices/{device.id}/members", {"username": "marius"}, format="json"
    )
    assert response.status_code == 403


def test_transfer_ownership(auth_client, device, user, other_user):
    device.add_member(other_user, role=Membership.Role.MEMBER)

    response = auth_client.post(
        f"/api/v1/devices/{device.id}/transfer", {"username": "camille"}, format="json"
    )
    assert response.status_code == 200
    assert device.role_of(other_user) == Membership.Role.OWNER
    assert device.role_of(user) == Membership.Role.MEMBER


def test_claim_creation_requires_staff(auth_client, user):
    response = auth_client.post(
        "/api/v1/devices/claims",
        {"device_id": "ghb-4d5e6f", "code": "ABC234"},
        format="json",
    )
    assert response.status_code == 403


def test_claim_creation_and_redemption_flow(user):
    staff = user.__class__.objects.create_superuser(
        username="admin", email="admin@example.com", password="motdepasse-long-3"
    )
    staff_client = APIClient()
    staff_client.force_authenticate(user=staff)

    created = staff_client.post(
        "/api/v1/devices/claims",
        {"device_id": "ghb-4d5e6f", "code": "ABC234", "name": "Bourgeon tunnel"},
        format="json",
    )
    assert created.status_code == 201
    assert created.json()["code"] == "ABC234"

    # Duplicate device id is refused.
    assert (
        staff_client.post(
            "/api/v1/devices/claims", {"device_id": "ghb-4d5e6f"}, format="json"
        ).status_code
        == 400
    )

    user_client = APIClient()
    user_client.force_authenticate(user=user)
    redeemed = user_client.post(
        "/api/v1/devices/claims/redeem", {"code": "abc234"}, format="json"
    )
    assert redeemed.status_code == 200
    assert redeemed.json()["status"] == Device.Status.PROVISIONED
    assert redeemed.json()["role"] == "owner"

    # The same code cannot be used again.
    second = user_client.post(
        "/api/v1/devices/claims/redeem", {"code": "ABC234"}, format="json"
    )
    assert second.status_code == 400
    assert second.json()["code"] == "already_claimed"


def test_redeem_unknown_code_counts_attempt(pending_device, user):
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(
        "/api/v1/devices/claims/redeem", {"code": "ZZZZZZ"}, format="json"
    )
    assert response.status_code == 400
    assert PairingClaim.objects.get(device=pending_device).attempts == 0


def test_sites_are_scoped_to_their_owner(auth_client, user, other_user):
    from devices.models import Site

    Site.objects.create(owner=user, name="Serre")
    Site.objects.create(owner=other_user, name="Jardin de Camille")

    payload = auth_client.get("/api/v1/sites").json()
    assert [site["name"] for site in payload["results"]] == ["Serre"]

    created = auth_client.post("/api/v1/sites", {"name": "Tunnel"}, format="json")
    assert created.status_code == 201
    assert Site.objects.get(name="Tunnel").owner == user
