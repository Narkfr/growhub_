"""Flask application exposing the live device state over HTTP + SSE."""

import flask

from .registry import DeviceRegistry
from .state import iter_events, state_payload


def create_app(registry=None, hub=None):
    """Build the Flask app.

    ``registry`` and ``hub`` are optional so tests can inject fakes; the
    production entry point (``__main__.py``) wires the real ones.
    """
    if registry is None:
        registry = DeviceRegistry()

    app = flask.Flask(__name__)

    @app.after_request
    def add_cors_headers(response):
        # The dashboard is served by Next.js (different origin); allow it.
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response

    @app.get("/api/health")
    def health():
        return flask.jsonify({"status": "ok", "devices": len(registry.snapshot())})

    @app.get("/api/state")
    def state():
        return flask.jsonify(state_payload(registry))

    @app.get("/api/stream")
    def stream():
        if hub is None:
            flask.abort(501, "SSE hub not wired")

        def generate():
            event_queue = hub.subscribe()
            try:
                yield from iter_events(registry, event_queue)
            finally:
                hub.unsubscribe(event_queue)

        return flask.Response(
            flask.stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    return app
