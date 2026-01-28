import pytest
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
