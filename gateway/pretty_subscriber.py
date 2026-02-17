import json
from datetime import datetime

import paho.mqtt.client as mqtt
from rich.console import Console
from rich.live import Live
from rich.table import Table

# Configuration
BROKER_IP = "localhost"
MQTT_USER = "pico_client"
MQTT_PASS = "your_password"  # Replace with your .env value
TOPIC = "growhub/telemetry"

console = Console()
current_data = {}


def on_message(client, userdata, msg):
    """Callback triggered when data is received."""
    global current_data
    try:
        payload = json.loads(msg.payload.decode())
        current_data = payload
    except Exception as e:
        console.print(f"[red]Error parsing JSON: {e}[/red]")


def generate_table() -> Table:
    """Generates a rich table with the latest data."""
    table = Table(
        title=f"🌱 GrowHub Live Monitor - {datetime.now().strftime('%H:%M:%S')}"
    )

    table.add_column("Sensor/Actuator", style="cyan", no_wrap=True)
    table.add_column("Metric", style="magenta")
    table.add_column("Value", style="green")

    # Parsing Sensors
    for sensor_id, metrics in current_data.items():
        if sensor_id == "actuators":
            continue

        for metric_name, metric_data in metrics.items():
            unit = (
                "%" if "moisture" in metric_name or "humidity" in metric_name else "°C"
            )
            table.add_row(
                sensor_id, metric_name.capitalize(), f"{metric_data.value} {unit}"
            )

    # Parsing Actuators
    if "actuators" in current_data:
        table.add_section()
        for act_id, state in current_data["actuators"].items():
            color = "bold green" if state == "ON" else "bold red"
            table.add_row(act_id, "Status", f"[{color}]{state}[/{color}]")

    return table


# MQTT Client Setup
client = mqtt.Client()
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.on_message = on_message

try:
    client.connect(BROKER_IP, 1883, 60)
    client.subscribe(TOPIC)
    client.loop_start()

    # UI Live Update Loop
    with Live(generate_table(), refresh_per_second=1) as live:
        while True:
            live.update(generate_table())
except KeyboardInterrupt:
    client.disconnect()
    console.print("\n[yellow]Monitoring stopped.[/yellow]")
