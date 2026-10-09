import json
import os

import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

load_dotenv()

# Configuration InfluxDB
INFLUX_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUXDB_TOKEN")
INFLUX_ORG = os.getenv("INFLUXDB_ORG")
INFLUX_BUCKET = os.getenv("INFLUXDB_BUCKET")

# Configuration MQTT
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

# Init InfluxDB Client
influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = influx_client.write_api(write_options=SYNCHRONOUS)


def handle_sensors(client_id, payload):
    """Range les données de télémétrie en extrayant la valeur numérique."""
    for sensor_id, metrics in payload.items():
        if sensor_id == "actuators":
            continue

        if not isinstance(metrics, dict):
            # A sensor can return None when its read fails (e.g. DHT11
            # timeout); skip it so one failing sensor doesn't drop the
            # whole telemetry record.
            print(f"Skipping {sensor_id}: no data")
            continue

        point = Point("environment").tag("device", client_id).tag("sensor", sensor_id)

        for metric, data in metrics.items():
            # Si data est un dictionnaire (ex: {'value': 18, 'unit': 'celsius'})
            if isinstance(data, dict) and "value" in data:
                val = data["value"]
            else:
                # Si c'est déjà une valeur simple
                val = data

            try:
                point.field(metric, float(val))
            except (TypeError, ValueError) as e:
                print(f"Skipping {metric}: {val} is not a number. Error: {e}")
                continue
        write_api.write(bucket=INFLUX_BUCKET, record=point)


def handle_actuator_event(client_id, target_id, payload):
    """Range les événements de changement d'état (ON/OFF)"""
    state_str = payload.get("state", "OFF")
    state_bool = 1 if state_str == "ON" else 0

    point = (
        Point("actuators_events")
        .tag("device", client_id)
        .tag("actuator", target_id)
        .field("state", state_bool)
    )

    write_api.write(bucket=INFLUX_BUCKET, record=point)


def handle_device_status(client_id, payload_bytes):
    """Record device online/offline transitions (from MQTT Last Will)."""
    status = payload_bytes.decode().strip().lower()
    online = 1 if status == "online" else 0
    point = Point("device_status").tag("device", client_id).field("online", online)
    write_api.write(bucket=INFLUX_BUCKET, record=point)
    print(f"Device {client_id} is {'online' if online else 'offline'}")


def on_message(client, userdata, msg):
    try:
        topic_parts = msg.topic.split("/")
        client_id = topic_parts[0]
        category = topic_parts[1]  # 'telemetry', 'data' or 'status'

        # Device status is a plain string ("online"/"offline"), not JSON.
        if category == "status":
            handle_device_status(client_id, msg.payload)
            return

        payload = json.loads(msg.payload.decode())

        if category == "telemetry":
            handle_sensors(client_id, payload)
        elif category == "data":
            # Topic format: client_id/data/target_id/state
            target_id = topic_parts[2]
            handle_actuator_event(client_id, target_id, payload)

    except Exception as e:
        print(f"Error processing message: {e}")


# Init MQTT Client
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "TelemetryLogger")
mqtt_client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
mqtt_client.on_message = on_message

print(f"Connecting to MQTT broker at {MQTT_BROKER}...")
mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
mqtt_client.subscribe("+/telemetry")
mqtt_client.subscribe("+/data/+/state")
mqtt_client.subscribe("+/status")

print("Logger is active. Waiting for data...")
mqtt_client.loop_forever()
