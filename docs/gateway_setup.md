# GrowHub Gateway Setup Guide

This document describes the process of setting up the GrowHub central gateway using a Dockerized stack (MQTT, InfluxDB, PostgreSQL) on a Raspberry Pi 4 or local development machine.

## 1. Project Structure
The gateway logic and data persistence are organized as follows:
```text
GrowHub/
├── gateway/
│   ├── mosquitto/
│   │   ├── config/      # mosquitto.conf
│   │   ├── data/        # Persistent MQTT data
│   │   └── log/         # Service logs
│   ├── telemetry_logger.py  # Bridge MQTT -> InfluxDB
│   ├── docker-compose.yml
│   └── .env             # Environment variables (not tracked by git)
```

## 2. Prerequisites
- Raspberry Pi 4 or Local Dev Machine (Linux/macOS/Windows)
- Docker and Docker Compose installed
- Python 3.11+ with `venv` activated
- Python libraries: `influxdb-client`, `paho-mqtt`, `python-dotenv`

## 3. Installation Steps

### 3.1 Environment Configuration
Create a `.env` file in the `gateway/` directory. **Critical: Do not use spaces around the `=` sign.**

```ini
# System Permissions (run 'id' in terminal)
UID=1000
GID=1000

# MQTT Broker
MQTT_USER=your_user_here
MQTT_PASSWORD=your_secure_password
MQTT_PORT=1883

# PostgreSQL (Planning & ITK)
POSTGRES_USER=your_user_here
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=growhub

# InfluxDB (Telemetry)
INFLUXDB_USER=your_user_here
INFLUXDB_PASSWORD=your_secure_password
INFLUXDB_ORG=growhub_org
INFLUXDB_BUCKET=telemetry
INFLUXDB_TOKEN=generate_this_after_first_run
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
touch mosquitto/config/password_file

#### Create the MQTT user using credentials from .env
source .env
docker exec -it growhub-mqtt mosquitto_passwd -b /mosquitto/config/password_file $MQTT_USER $MQTT_PASSWORD

#### Restart the broker to apply security settings
docker compose restart

### 3.3 Deployment
Launch the stack.

```bash
cd gateway
docker compose up -d
```

## 4. Database Access

### 4.1 InfluxDB (Time Series)
- **URL**: `http://localhost:8086`
- **Setup**: Log in with credentials from `.env`.
- **Token**: Go to `Load Data > API Tokens` to generate a token and update your `.env`.

### 4.2 PostgreSQL (Relational) via Adminer
- **URL**: `http://localhost:8080`
- **System**: PostgreSQL
- **Server**: `postgres`
- **Credentials**: Use `POSTGRES_USER` and `POSTGRES_PASSWORD`.

## 5. Telemetry Logger Setup

The `telemetry_logger.py` acts as a bridge, subscribing to MQTT topics and writing data to InfluxDB.

1. Install dependencies:
   ```bash
   pip install influxdb-client paho-mqtt python-dotenv
   ```
2. Run the logger:
   ```bash
   python3 telemetry_logger.py
   ```

## 6. Testing & Troubleshooting

### 6.1 Check Container Status
```bash
docker compose ps
```

### 6.2 View Logs
```bash
# General logs
docker compose logs -f

# Specific service logs
docker logs growhub-postgres
docker logs growhub-influx
```

### 6.3 MQTT Smoke Test
```bash
# Subscribe to telemetry (from another terminal)
docker exec -it growhub-mqtt mosquitto_sub -t "+/telemetry" -u $MQTT_USER -P $MQTT_PASSWORD
```

## 7. Port Mapping Summary
| Service | Internal Port | External Port | Description |
| :--- | :--- | :--- | :--- |
| Mosquitto | 1883 | 1883 | MQTT Broker |
| InfluxDB | 8086 | 8086 | Telemetry Database |
| PostgreSQL | 5432 | 5433 | Relational Database |
| Adminer | 8080 | 8080 | Database Management UI |
