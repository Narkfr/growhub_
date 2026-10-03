# GrowHub Gateway Setup Guide

This document describes the process of setting up the GrowHub central gateway using a Dockerized stack (MQTT, InfluxDB, PostgreSQL) on a Raspberry Pi 4 or local development machine.

## 1. Project Structure
The gateway logic and data persistence are organized as follows:
```text
GrowHub/
├── gateway/
│   ├── itk/             # JSON files for Technical Itineraries
│   ├── mosquitto/
│   │   ├── config/      # mosquitto.conf & pwfile
│   │   ├── data/        # Persistent MQTT data
│   │   └── log/         # Service logs
│   ├── init_db.py       # PostgreSQL schema initialization
│   ├── sync_itk.py      # JSON to SQL synchronization script
│   ├── telemetry_logger.py  # Bridge: MQTT -> InfluxDB
│   ├── logic_engine.py  # Automation & Decision Engine
│   ├── docker-compose.yml
│   └── .env             # Environment variables
```

## 2. Prerequisites
- Raspberry Pi 4 or Local Machine (Linux/macOS/Windows)
- Docker and Docker Compose installed
- Python 3.11+ with a virtual environment (`venv`) activated
- Python libraries: `influxdb-client`, `paho-mqtt`, `python-dotenv`, `psycopg2-binary`, `apscheduler`

## 3. Initial Configuration

### 3.1 Environment File (.env)
Create a `.env` file in the `gateway/` directory. **Important: Do not use spaces around the `=` sign.**

```ini
# System Permissions
UID=1000
GID=1000

# MQTT Broker
MQTT_BROKER=localhost
MQTT_USER=your_user
MQTT_PASSWORD=your_password
MQTT_PORT=1883

# PostgreSQL (Planning & ITK)
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
POSTGRES_DB=growhub

# InfluxDB (Telemetry)
INFLUXDB_URL=http://localhost:8086
INFLUXDB_TOKEN=your_api_token
INFLUXDB_ORG=growhub_org
INFLUXDB_BUCKET=telemetry
```

### 3.2 Mosquitto Configuration
Create `mosquitto/config/mosquitto.conf`:
```ini
listener 1883 0.0.0.0
allow_anonymous false
password_file /mosquitto/config/pwfile
persistence true
persistence_location /mosquitto/data/
log_dest file /mosquitto/log/mosquitto.log
log_dest stdout
```
#### Ensure the configuration file exists
```touch mosquitto/config/password_file```

#### Create the MQTT user using credentials from .env
```source .env
docker exec -it growhub-mqtt mosquitto_passwd -b /mosquitto/config/password_file $MQTT_USER $MQTT_PASSWORD
```

#### Restart the broker to apply security settings
```docker compose restart```

### 3.3 Docker Deployment
Start the infrastructure services:
```bash
cd gateway
docker compose up -d
```

## 4. Database Initialization

### 4.1 PostgreSQL
1.  **Schema**: Run the initialization script to create the `itks`, `itk_phases`, and `devices` tables:
    ```bash
    python3 init_db.py
    ```
2.  **ITK Synchronization**: Place your configuration files in the `itk/` folder and sync them to the database:
    ```bash
    python3 sync_itk.py
    ```

### 4.2 InfluxDB
Log in to `http://localhost:8086` to generate your API Token and update the `INFLUXDB_TOKEN` in your `.env` file.

## 5. Gateway Services

### 5.1 Telemetry Logger (`telemetry_logger.py`)
This service listens for MQTT messages on the `+/telemetry` topic and records sensor data into InfluxDB. It automatically handles nested JSON values (value/unit format).
```bash
python3 telemetry_logger.py
```

### 5.2 Logic Engine (`logic_engine.py`)
This service handles autonomous decision-making for devices in `AUTO` mode:
- **Reactive Logic**: Triggers irrigation if soil moisture drops below the threshold defined in the current ITK phase.
- **Scheduled Logic**: Manages lighting cycles (`GrowLamp`) based on `light_start_hour` and `light_hours` defined in the ITK.
```bash
python3 logic_engine.py
```

## 6. Port Mapping Summary
| Service | Internal Port | External Port | Description |
| :--- | :--- | :--- | :--- |
| Mosquitto | 1883 | 1883 | MQTT Broker |
| InfluxDB | 8086 | 8086 | Time Series Database |
| PostgreSQL | 5432 | 5433 | Relational Database |
| Adminer | 8080 | 8080 | SQL Management UI |
| Grafana | 3000 | 3000 | Visualization Dashboards |

## 7. Useful MQTT Commands
- **Subscribe to Telemetry**: `mosquitto_sub -h localhost -t "+/telemetry" -u $USER -P $PASSWORD`
- **Manual Actuator Command**: `mosquitto_pub -h localhost -t "DeviceID/actuators/ActuatorID/action" -m "ON" -u $USER -P $PASSWORD`

## 8. Security

### Per-device credentials
Each GrowHub device must authenticate with its OWN MQTT account — never
share one account across devices, so a compromised device can be revoked
individually.

```bash
source .env
docker exec -it growhub-mqtt mosquitto_passwd -b /mosquitto/config/password_file growhub_device1 <password1>
docker exec -it growhub-mqtt mosquitto_passwd -b /mosquitto/config/password_file growhub_device2 <password2>
docker compose restart
```

Then set `MQTT_USER` / `MQTT_PASSWORD` in each device's `firmware/secrets.py`
to that device's own credentials.

### TLS (deferred)
The broker currently runs plain MQTT on port 1883, which is acceptable on a
trusted local network. If the gateway is ever exposed beyond the LAN, enable
TLS (port 8883) with per-device certificates. This is intentionally deferred
for the MVP — see the project roadmap.
