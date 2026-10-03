"""Pure helpers to shape registry state for the HTTP API.

No I/O and no third-party imports here, so this module is unit-testable
without mocking Flask or paho-mqtt.
"""

import json
import queue
import time

# A device that hasn't sent anything for this long is dropped from the live
# view — it is no longer actively sending data.
STALE_AFTER_SECONDS = 300


def state_payload(registry, stale_after=STALE_AFTER_SECONDS):
    """Build the JSON body for ``GET /api/state`` from a registry.

    Devices not seen within ``stale_after`` seconds are filtered out so the
    dashboard only shows what is currently being received.
    """
    devices = [
        device
        for device in registry.snapshot()
        if device["last_seen"] is not None
        and time.time() - device["last_seen"] <= stale_after
    ]
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
