# Gateway Setup Guide (Raspberry Pi 4)

This document describes the process of setting up the GrowHub central gateway, including the Dockerized MQTT broker and security configurations.

## 1. Project Structure
The gateway logic is organized in the `gateway/` directory:
```text
GrowHub/
├── gateway/
│   ├── mosquitto/
│   │   ├── config/      # Configuration files (mosquitto.conf, password_file)
│   │   ├── data/        # Persistent MQTT data
│   │   └── log/         # Service logs
│   ├── docker-compose.yml
│   └── .env             # Environment variables (not tracked by git)
```

## 2. Prerequisites
- Raspberry Pi 4 running Raspberry Pi OS
- Docker and Docker Compose installed
- Python 3.11+ with `python-dotenv` and `paho-mqtt` libraries

## 3. Installation Steps

### 3.1 Environment Configuration
Create a `.env` file in the `gateway/` directory based on `.env.example`:
```bash
MQTT_BROKER=broker_IP_address_here
MQTT_USER=pico_client
MQTT_PASSWORD=your_secure_password
MQTT_PORT=1883
```

### 3.2 Deployment
Start the MQTT broker in detached mode:
```bash
cd gateway
docker compose up -d
```

### 3.3 Security Configuration (First run only)
```bash
# Ensure the configuration file exists
touch mosquitto/config/password_file

# Create the MQTT user using credentials from .env
source .env
docker exec -it growhub-mqtt mosquitto_passwd -b /mosquitto/config/password_file $MQTT_USER $MQTT_PASSWORD

# Restart the broker to apply security settings
docker compose restart
```

## 4. Testing Connectivity

### 4.1 Local Smoke Test (Internal)
To verify that the broker is working correctly, open two separate SSH shells on your Raspberry Pi or remote machine.

**Shell 1 (The Subscriber):**
This shell will wait for messages on the test topic.
```bash
source .env
docker exec -it growhub-mqtt mosquitto_sub -h localhost -t "growhub/test" -u $MQTT_USER -P $MQTT_PASSWORD
```

**Shell 2 (The Publisher):**
Send a message from this shell. It should appear instantly in Shell 1.
```bash
source .env
docker exec -it growhub-mqtt mosquitto_pub -h localhost -t "growhub/test" -m "Hello from RPi Shell" -u $MQTT_USER -P $MQTT_PASSWORD
```

### 4.2 Remote Test (External)
Run the Python test script from your development machine to ensure port 1883 is accessible over the network:
```bash
python3 tools/gateway/mqtt.py
```

## 5. Troubleshooting & Logs
```bash
# View real-time logs
docker logs -f growhub-mqtt

# Check resource usage
docker stats growhub-mqtt
```
