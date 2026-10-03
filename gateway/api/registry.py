"""In-memory registry of the latest state of every GrowHub device.

The MQTT bridge feeds this registry as messages arrive; the Flask API reads it
to serve the live dashboard. All mutations are guarded by a lock because
paho-mqtt callbacks run on their own thread.
"""

import copy
import queue
import threading
import time


def normalize_metric(value):
    """Normalize a single telemetry metric into ``{"value", "unit"}``.

    A metric can arrive as ``{"value": 42, "unit": "percent"}``, as a bare
    number (``42``), or as ``None`` (the sensor read failed). Returns ``None``
    when there is no usable value so the caller can drop it.
    """
    if value is None:
        return None
    if isinstance(value, dict):
        val = value.get("value")
        if val is None:
            return None
        return {"value": val, "unit": value.get("unit")}
    return {"value": value, "unit": None}


def parse_telemetry(payload):
    """Split a telemetry payload into ``(sensors, actuators)`` dicts.

    The Pico publishes on ``{client_id}/telemetry``::

        {
            "ClimateSensor": {"temperature": {"value": 18, "unit": "celsius"}, ...},
            "SoilSensor": {"moisture": {"value": 42, "unit": "percent"}},
            "actuators": {"WaterPump": "ON", "GrowLamp": "OFF"},
        }

    Individual sensors can be ``None`` (failed read) or non-dict values; both
    are dropped rather than aborting the whole record.
    """
    sensors = {}
    for sensor_id, metrics in payload.items():
        if sensor_id == "actuators" or not isinstance(metrics, dict):
            continue
        normalized = {}
        for metric, value in metrics.items():
            entry = normalize_metric(value)
            if entry is not None:
                normalized[metric] = entry
        if normalized:
            sensors[sensor_id] = normalized

    raw_actuators = payload.get("actuators")
    actuators = {}
    if isinstance(raw_actuators, dict):
        actuators = {
            act_id: ("ON" if state == "ON" else "OFF")
            for act_id, state in raw_actuators.items()
        }
    return sensors, actuators


class DeviceRegistry:
    """Thread-safe store of the most recent state per device (client id)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._devices = {}

    def _device(self, client_id):
        """Return (creating if needed) the device dict. Call under the lock."""
        dev = self._devices.get(client_id)
        if dev is None:
            dev = {
                "id": client_id,
                "status": "unknown",
                "last_seen": None,
                "sensors": {},
                "actuators": {},
            }
            self._devices[client_id] = dev
        return dev

    def apply_telemetry(self, client_id, payload):
        """Merge a full telemetry payload for one device."""
        sensors, actuators = parse_telemetry(payload)
        with self._lock:
            dev = self._device(client_id)
            dev["sensors"] = sensors
            dev["actuators"].update(actuators)
            dev["last_seen"] = time.time()
            if dev["status"] == "unknown":
                dev["status"] = "online"
        return client_id

    def apply_actuator_event(self, client_id, actuator_id, payload):
        """Merge a single actuator state change (``{client_id}/data/+/state``)."""
        state = "ON" if payload.get("state") == "ON" else "OFF"
        with self._lock:
            dev = self._device(client_id)
            dev["actuators"][actuator_id] = state
            dev["last_seen"] = time.time()
        return client_id

    def apply_status(self, client_id, raw):
        """Merge an online/offline transition (``{client_id}/status``)."""
        if isinstance(raw, (bytes, bytearray)):
            text = raw.decode().strip().lower()
        else:
            text = str(raw).strip().lower()
        online = text == "online"
        with self._lock:
            dev = self._device(client_id)
            dev["status"] = "online" if online else "offline"
            dev["last_seen"] = time.time()
        return client_id

    def snapshot(self):
        """Return a deep-copied list of device dicts, sorted by client id."""
        with self._lock:
            return copy.deepcopy([self._devices[k] for k in sorted(self._devices)])


class EventHub:
    """Fan-out of state updates to SSE subscribers (thread-safe).

    Each subscriber gets its own queue; publishing enqueues the payload onto
    every active queue without blocking the MQTT callback thread.
    """

    def __init__(self):
        self._queues = []
        self._lock = threading.Lock()

    def subscribe(self):
        q = queue.Queue()
        with self._lock:
            self._queues.append(q)
        return q

    def unsubscribe(self, q):
        with self._lock:
            if q in self._queues:
                self._queues.remove(q)

    def publish(self, payload):
        with self._lock:
            queues = list(self._queues)
        for q in queues:
            q.put(payload)
