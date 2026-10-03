import sys
import types

import pytest

# --- Fake flask (the app is thin wiring; we verify routes register and return
#     the right payload shapes without pulling in the real framework). --------


class FakeResponse:
    def __init__(self, body=None, status=200, **kwargs):
        self.body = body
        self.status = status
        self.headers = kwargs.get("headers", {})
        self.mimetype = kwargs.get("mimetype")


class FakeFlask:
    def __init__(self, import_name):
        self.import_name = import_name
        self.routes = {}
        self.after_request_fn = None

    def after_request(self, fn):
        self.after_request_fn = fn
        return fn

    def get(self, path):
        def decorator(fn):
            self.routes[path] = fn
            return fn

        return decorator


class _Abort(Exception):
    pass


_flask = types.ModuleType("flask")
_flask.Flask = FakeFlask
_flask.jsonify = lambda payload: payload
_flask.Response = FakeResponse
_flask.stream_with_context = lambda gen: gen
_flask.abort = lambda *args, **kwargs: (_ for _ in ()).throw(_Abort(args))
sys.modules["flask"] = _flask

from gateway.api import app as app_module  # noqa: E402
from gateway.api.registry import DeviceRegistry, EventHub  # noqa: E402


def _app():
    return app_module.create_app(registry=DeviceRegistry())


def test_health_route():
    app = _app()
    payload = app.routes["/api/health"]()
    assert payload == {"status": "ok", "devices": 0}


def test_state_route():
    app = _app()
    reg = DeviceRegistry()
    reg.apply_status("dev1", b"online")
    app = app_module.create_app(registry=reg)
    payload = app.routes["/api/state"]()
    assert payload["count"] == 1
    assert payload["devices"][0]["id"] == "dev1"


def test_stream_route_yields_snapshot():
    reg = DeviceRegistry()
    reg.apply_status("dev1", b"online")
    hub = EventHub()
    app = app_module.create_app(registry=reg, hub=hub)
    response = app.routes["/api/stream"]()
    first_frame = next(response.body)
    assert first_frame.startswith("data: ")
    assert "dev1" in first_frame


def test_stream_route_without_hub_aborts():
    app = app_module.create_app(registry=DeviceRegistry(), hub=None)
    with pytest.raises(_Abort):
        app.routes["/api/stream"]()
