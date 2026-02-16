import os
import time
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

# Path management: locate the .env file relative to this script
# Adjust the number of parents depending on your structure
# Here we assume .env is in the 'gateway/' folder
current_dir = Path(__file__).resolve().parent
env_path = current_dir.parent.parent / "gateway" / ".env"

# Load the environment variables
load_dotenv(dotenv_path=env_path)

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
TOPIC = "growhub/test"


def on_connect(client, userdata, flags, rc):
    """Callback triggered when the client connects to the broker."""
    if rc == 0:
        print("Connected successfully to broker")
        client.subscribe(TOPIC)
    else:
        print(f"Connection failed with code {rc}")


def on_message(client, userdata, msg):
    """Callback triggered when a message is received on a subscribed topic."""
    print(f"Message received: {msg.payload.decode()} on topic {msg.topic}")


client = mqtt.Client()
client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
client.on_connect = on_connect
client.on_message = on_message

print(f"Attempting to connect to {MQTT_BROKER}...")
try:
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
except Exception as e:
    print(f"Could not connect: {e}")
    exit(1)

# Start network loop in a separate thread
client.loop_start()

try:
    while True:
        payload = f"Test message sent at {time.time()}"
        print(f"Publishing: {payload}")
        client.publish(TOPIC, payload)
        time.sleep(5)
except KeyboardInterrupt:
    print("Test interrupted by user")
    client.loop_stop()
    client.disconnect()
