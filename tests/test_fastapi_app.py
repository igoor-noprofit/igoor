import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from fastapi_app import create_app
from plugin_manager import PluginManager


@pytest.fixture
def client(monkeypatch):
    async def _noop_trigger(self, *args, **kwargs):
        return None

    monkeypatch.setattr(PluginManager, "trigger_hook", _noop_trigger, raising=False)

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_plugins_by_category_endpoint(client):
    response = client.get("/api/plugins/by-category")
    assert response.status_code == 200
    assert isinstance(response.json(), dict)


def test_change_view_endpoint(client):
    response = client.post(
        "/api/app/change-view",
        json={"lastview": "daily", "view": "flow"},
    )
    assert response.status_code == 204


def test_websocket_endpoint_accepts_connection(client):
    with client.websocket_connect("/ws/app") as websocket:
        websocket.send_text('{"socket": "ready"}')


# === Auth Tests ===

@pytest.fixture
def client_with_auth_disabled(monkeypatch):
    """Client with IGOOR_ACCESS_FROM_OUTSIDE=False (default, localhost-only)."""
    async def _noop_trigger(self, *args, **kwargs):
        return None

    monkeypatch.setenv("IGOOR_ACCESS_FROM_OUTSIDE", "False")
    monkeypatch.setattr(PluginManager, "trigger_hook", _noop_trigger, raising=False)

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def client_with_auth_enabled(monkeypatch):
    """Client with IGOOR_ACCESS_FROM_OUTSIDE=True and mocked token."""
    async def _noop_trigger(self, *args, **kwargs):
        return None

    monkeypatch.setenv("IGOOR_ACCESS_FROM_OUTSIDE", "True")
    monkeypatch.setattr(PluginManager, "trigger_hook", _noop_trigger, raising=False)

    # Mock the SettingsManager to return a predictable token
    mock_token = "test-token-12345"
    with patch("fastapi_app.SettingsManager") as MockSettingsManager:
        mock_instance = MockSettingsManager.return_value
        mock_instance.get_or_create_access_token.return_value = mock_token

        app = create_app()
        with TestClient(app) as test_client:
            yield test_client, mock_token


def test_auth_disabled_allows_all(client_with_auth_disabled):
    """With auth disabled, all routes should return 200."""
    response = client_with_auth_disabled.get("/")
    assert response.status_code == 200

    response = client_with_auth_disabled.get("/api/plugins/by-category")
    assert response.status_code == 200


def test_auth_enabled_redirects_to_login(client_with_auth_enabled):
    """With auth enabled and no cookie, GET / redirects to /login."""
    client, _ = client_with_auth_enabled
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/login"


def test_auth_enabled_api_returns_401(client_with_auth_enabled):
    """With auth enabled and no cookie, API routes return 401."""
    client, _ = client_with_auth_enabled
    response = client.get("/api/plugins/by-category")
    assert response.status_code == 401
    assert response.json() == {"error": "Unauthorized"}


def test_login_page_is_public(client_with_auth_enabled):
    """Login page should always be accessible."""
    client, _ = client_with_auth_enabled
    response = client.get("/login")
    assert response.status_code == 200


def test_health_is_public(client_with_auth_enabled):
    """Health endpoint should always be accessible."""
    client, _ = client_with_auth_enabled
    response = client.get("/health")
    assert response.status_code == 200


def test_login_with_valid_token(client_with_auth_enabled):
    """Login with correct token should set cookie and redirect."""
    client, mock_token = client_with_auth_enabled

    # Patch SettingsManager in the module scope where login endpoint uses it
    with patch("settings_manager.SettingsManager") as MockSM:
        mock_instance = MockSM.return_value
        mock_instance.get_or_create_access_token.return_value = mock_token
        response = client.post(
            "/api/auth/login",
            data={"token": mock_token},
            follow_redirects=False
        )

    assert response.status_code == 303
    assert "igoor_session" in response.cookies
    assert response.cookies["igoor_session"] == mock_token


def test_login_with_invalid_token(client_with_auth_enabled):
    """Login with wrong token should return 401."""
    client, mock_token = client_with_auth_enabled

    with patch("fastapi_app.SettingsManager") as MockSM:
        MockSM.return_value.get_or_create_access_token.return_value = mock_token
        response = client.post(
            "/api/auth/login",
            data={"token": "wrong-token"},
            follow_redirects=False
        )

    assert response.status_code == 401


def test_authenticated_access(client_with_auth_enabled):
    """With valid cookie, protected routes should work."""
    client, mock_token = client_with_auth_enabled

    # Access with cookie set
    response = client.get(
        "/api/plugins/by-category",
        cookies={"igoor_session": mock_token}
    )
    assert response.status_code == 200
