"""Session authentication, as the web front uses it.

The dashboard is a SPA behind the same origin: it logs in with a session cookie
and must therefore hold a CSRF token for every unsafe request. These tests pin
both halves of that contract — the session and the cookie.
"""

import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db

PASSWORD = "motdepasse-long-1"


@pytest.fixture
def write_client():
    """Same as `client`, but Django enforces CSRF as it does in production."""
    return Client(enforce_csrf_checks=True)


def test_login_opens_a_session(client, user):
    response = client.post(
        "/api/v1/auth/login",
        {"username": "marius", "password": PASSWORD},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["username"] == "marius"
    assert client.session["_auth_user_id"] == str(user.pk)


def test_login_refuses_bad_credentials(client, user):
    response = client.post(
        "/api/v1/auth/login",
        {"username": "marius", "password": "faux"},
        content_type="application/json",
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Identifiants invalides."


def test_errors_are_json_even_for_a_browser(client, user):
    """Un navigateur annonce préférer `text/html` : l'erreur doit rester du JSON.

    Sinon DRF sert sa page « browsable API », le SPA échoue à la lire et affiche
    « Impossible de joindre l'API » au lieu de la vraie raison — constaté sur le
    tableau de bord en production.
    """
    browser = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"

    response = client.post(
        "/api/v1/auth/login",
        {"username": "marius", "password": "faux"},
        content_type="application/json",
        HTTP_ACCEPT=browser,
    )
    assert response.status_code == 401
    assert response["Content-Type"].startswith("application/json")
    assert response.json()["detail"] == "Identifiants invalides."

    anonymous = client.get("/api/v1/auth/me", HTTP_ACCEPT=browser)
    assert anonymous["Content-Type"].startswith("application/json")


def test_login_refuses_an_inactive_account(client, user):
    user.is_active = False
    user.save(update_fields=["is_active"])

    response = client.post(
        "/api/v1/auth/login",
        {"username": "marius", "password": PASSWORD},
        content_type="application/json",
    )

    assert response.status_code == 401


def test_me_returns_the_profile(client, user):
    client.force_login(user)
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "marius"
    assert body["email"] == "marius@example.com"


def test_me_requires_a_session(client):
    assert client.get("/api/v1/auth/me").status_code == 403


def test_me_hands_the_spa_its_csrf_cookie(client, user):
    """Without this cookie the front cannot POST anything (DRF + session auth)."""
    client.force_login(user)
    response = client.get("/api/v1/auth/me")

    assert "csrftoken" in response.cookies


def test_logout_closes_the_session(client, user):
    client.force_login(user)
    response = client.post("/api/v1/auth/logout")

    assert response.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 403


def test_logout_requires_a_session(client):
    assert client.post("/api/v1/auth/logout").status_code == 403


def test_csrf_is_enforced_on_unsafe_methods(write_client, user):
    """A forged POST from another site must be refused, cookie or not."""
    write_client.force_login(user)
    response = write_client.post(
        "/api/v1/devices/claims/redeem",
        {"code": "ABC234"},
        content_type="application/json",
    )

    assert response.status_code == 403
    assert "CSRF" in response.content.decode()


def test_urls_are_named_for_reverse():
    assert reverse("auth-login") == "/api/v1/auth/login"
    assert reverse("auth-me") == "/api/v1/auth/me"
