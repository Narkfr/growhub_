"""Pure helpers to shape registry state for the HTTP API.

No I/O and no third-party imports here, so this module is unit-testable
without mocking Flask or paho-mqtt.
"""

import json
import queue


def state_payload(registry):
    """Build the JSON body for ``GET /api/state`` from a registry."""
    devices = registry.snapshot()
    return {"devices": devices, "count": len(devices)}


def format_sse(data):
    """Serialize one SSE ``data`` frame as a string."""
    return f"data: {json.dumps(data)}\n\n"


def iter_events(registry, event_queue, heartbeat_seconds=15):
    """Yield SSE frames: an initial snapshot, then live updates.

    Blocks on ``event_queue`` until a new MQTT message is published or the
    heartbeat fires (to keep proxies from timing out the connection). Yields
    plain strings ready to be written to the response.
    """
    yield format_sse(state_payload(registry))
    while True:
        try:
            payload = event_queue.get(timeout=heartbeat_seconds)
        except queue.Empty:
            yield ": keepalive\n\n"
        else:
            yield format_sse(payload)
