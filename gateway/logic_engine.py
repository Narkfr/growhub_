import json
import os
import threading
from datetime import datetime

import paho.mqtt.client as mqtt
import psycopg2
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

# Configuration loading
load_dotenv()

# Database connection parameters
DB_PARAMS = {
    "host": os.getenv("POSTGRES_HOST"),
    "port": int(os.getenv("POSTGRES_PORT", 5432)),
    "database": os.getenv("POSTGRES_DB"),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD"),
}


# Per-thread connection cache: paho callbacks and the APScheduler job run in
# different threads, so a single shared connection would not be safe.
_local = threading.local()


def get_db_connection():
    """Return a per-thread cached connection, reconnecting if closed."""
    conn = getattr(_local, "conn", None)
    if conn is None or conn.closed:
        conn = psycopg2.connect(**DB_PARAMS)
        _local.conn = conn
    return conn


def send_command(client_id, actuator, action):
    """Sends a toggle or state command to the Pico via MQTT."""
    # We use a standard topic structure: client_id/actuators/actuator_id/command
    topic = f"{client_id}/actuators/{actuator}/action"
    mqtt_client.publish(topic, action)
    # print(f"[{datetime.now().strftime('%H:%M:%S')}] SENT -> {topic, action}")


# --- DATA FETCHING ---


def get_active_device_config(device_id):
    """Retrieves current ITK phase settings for a specific device."""
    conn = get_db_connection()
    cur = conn.cursor()
    query = """
        SELECT p.target_settings, d.mode
        FROM devices d
        JOIN itk_phases p ON d.current_phase_id = p.id
        WHERE d.id = %s
    """
    cur.execute(query, (device_id,))
    row = cur.fetchone()
    cur.close()
    return row  # Returns (settings_dict, mode_string)


# --- LOGIC COMPONENTS ---
#
# NOTE: the ITK also defines temp_min/temp_max, but there is no ventilation
# or heating actuator wired yet, so temperature is recorded (telemetry) but
# not acted upon. See the roadmap in README.md.


def handle_lighting(device_id, settings):
    """Calculates if lights should be ON/OFF based on start_hour and duration."""
    start_h = settings.get("light_start_hour", 8)
    duration = settings.get("light_hours", 0)
    print(f"[{device_id}] Light Check: Start {start_h}h for {duration}h")

    if duration == 0:
        set_actuator(device_id, "GrowLamp", "off")
        return

    now_h = datetime.now().hour
    end_h = (start_h + duration) % 24

    # Logic to handle cycles spanning across midnight
    should_be_on = False
    if start_h < end_h:
        should_be_on = start_h <= now_h < end_h
    else:  # Overnight cycle (e.g., 22h to 06h)
        should_be_on = now_h >= start_h or now_h < end_h

    action = "on" if should_be_on else "off"
    set_actuator(device_id, "GrowLamp", action)


# Moisture hysteresis band (%): pump turns ON strictly below the target and
# OFF only once moisture rises this far above it, preventing rapid flapping.
MOISTURE_HYSTERESIS = 5
# Minimum actuator run time (seconds) before it may be switched back off.
MIN_RUN_SECONDS = 30

_actuator_state = {}  # (device_id, actuator) -> "on" | "off"
_actuator_changed_at = {}  # (device_id, actuator) -> datetime


def set_actuator(device_id, actuator, desired):
    """Send a command only when it actually changes the actuator state.

    Avoids re-sending the same command every tick and enforces a minimum
    runtime before an actuator can be switched back off.
    """
    key = (device_id, actuator)
    current = _actuator_state.get(key, "off")
    if desired is None or desired == current:
        return

    now = datetime.now()
    if current == "on" and desired == "off":
        started = _actuator_changed_at.get(key, now)
        if (now - started).total_seconds() < MIN_RUN_SECONDS:
            return

    send_command(device_id, actuator, desired)
    _actuator_state[key] = desired
    _actuator_changed_at[key] = now


def handle_moisture(device_id, settings, current_moisture):
    """Triggers watering if moisture drops below the ITK phase target."""
    target = settings.get("moisture_target", 50)

    if current_moisture < target:
        desired = "on"
    elif current_moisture > target + MOISTURE_HYSTERESIS:
        desired = "off"
    else:
        desired = None  # inside the hysteresis band: keep current state

    set_actuator(device_id, "WaterPump", desired)


# --- PERIODIC TASKS ---


def run_scheduled_logic():
    """Triggered every minute to sync time-based actuators (lights)."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM devices WHERE mode = 'AUTO'")
    devices = cur.fetchall()
    cur.close()

    for (device_id,) in devices:
        config = get_active_device_config(device_id)
        if config:
            handle_lighting(device_id, config[0])


# --- MQTT CALLBACKS ---


def on_connect(client, userdata, flags, rc):
    """Callback triggered when the broker responds to our connection request."""
    if rc == 0:
        print("✅ Connected to MQTT Broker!")
        # On s'abonne ici pour être sûr que l'abonnement survit aux déconnexions
        client.subscribe("+/telemetry")
        print("Subscribed to topics: +/telemetry")
    else:
        print(f"❌ Connection failed with code {rc}")


def on_message(client, userdata, msg):
    """Processes incoming telemetry to trigger reactive logic."""
    try:
        topic_parts = msg.topic.split("/")
        client_id = topic_parts[0]
        payload = json.loads(msg.payload.decode())

        config = get_active_device_config(client_id)

        if not config:
            print(f"⚠️ No config found in DB for device: {client_id}")
            return

        if config[1] != "AUTO":
            print(f"ℹ️ Device {client_id} is in {config[1]} mode. Skipping logic.")
            return

        settings = config[0]

        # Reactive: Soil Moisture check
        if "SoilSensor" in payload:
            # On adapte ici selon la structure de ton JSON reçu
            m_val = payload["SoilSensor"].get("moisture", {}).get("value")
            if m_val is not None:
                handle_moisture(client_id, settings, m_val)

    except Exception as e:
        print(f"❌ Error in Logic Engine on_message: {e}")


# --- MAIN EXECUTION ---

mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "LogicEngine")
mqtt_client.username_pw_set(os.getenv("MQTT_USER"), os.getenv("MQTT_PASSWORD"))

# ON AJOUTE LE CALLBACK DE CONNEXION
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

# Scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(run_scheduled_logic, "interval", seconds=60)
scheduler.start()

print(f"Attempting to connect to {os.getenv('MQTT_BROKER')}...")
try:
    # On utilise bien les variables d'environnement
    mqtt_client.connect("localhost", 1883, keepalive=60)
except Exception as e:
    print(f"Could not connect to broker: {e}")

try:
    mqtt_client.loop_forever()
except KeyboardInterrupt:
    print("Shutting down...")
    scheduler.shutdown()
