# 🌿 Smart Greenhouse - Radish MVP

An automated monitoring and control system for high-speed radish cultivation (18-day varieties). This project leverages a modern IoT architecture with a distributed Edge-to-Gateway approach, focused on reliability and data persistence.

---

## 🚀 System Architecture

| Layer | Technology | Role |
| :--- | :--- | :--- |
| **Edge Device** | Raspberry Pi Pico W | Sensor data collection (MicroPython) and actuator control. |
| **Connectivity** | MQTT over Wi-Fi | Lightweight pub/sub protocol for JSON data transport. |
| **Gateway Hub** | Raspberry Pi 4 (Docker) | MQTT Broker (Mosquitto), Time-series DB (InfluxDB), and Logic Bridge. |
| **Interface** | Next.js / Tailwind | Real-time dashboard and historical growth analytics. |

---

## 📂 Project Structure (Clean Monorepo)

```text
smart-serre-radis/
├── firmware/         # Embedded MicroPython source code
│   ├── src/          # Core logic and drivers (sensors.py, etc.)
│   ├── lib/          # External MicroPython libraries
│   ├── boot.py       # Network initialization at startup
│   ├── main.py       # Main orchestrator (infinite loop)
│   └── config_culture.py # Agronomic parameters
├── gateway/          # Server-side infrastructure (RPi 4)
│   ├── mosquitto/    # MQTT Broker configuration
│   └── docker-compose.yml # Docker service orchestration
├── dashboard/        # Web Application (Next.js)
├── tests/            # Centralized Quality Control
│   ├── firmware/     # Unit tests and mocks for Pico W logic
│   └── gateway/      # Integration tests (MQTT, Database)
├── docs/             # Wiring diagrams and build documentation
└── .gitignore        # Local and sensitive file exclusions
```

---

## 🛠️ Development Workflow

### 1. Firmware Environment (Pico W)
* **Runtime**: MicroPython v1.22+.
* **IDE**: VS Code with the **MicroPico** extension.
* **Continuous Deployment**:
    * `projectRoot` set to `./firmware`.
    * **Sync-on-Save** enabled: Every file save (Ctrl+S) triggers an automatic synchronization to the Pico's flash memory.
    * **Isolation**: The `tests/` directory is located at the root level to ensure only production code is uploaded to the device.

### 2. Gateway Environment (RPi 4)
* **OS**: Raspberry Pi OS 64-bit Lite.
* **Access**: SSH via VS Code (Remote-SSH) for seamless remote coding.
* **Containerization**: Docker & Docker Compose for high portability and environment consistency.

---

## 📊 Hardware & Pinout (Phase 1)

### Sensors
* **Atmosphere (Temp/Hum)**: DHT11 (Digital).
* **Soil (Moisture)**: Capacitive Soil Moisture Sensor V2.0 (Analog).

### Wiring Map (Pico W)
| Sensor | Pico Pin | GPIO | Role |
| :--- | :--- | :--- | :--- |
| **DHT11 Data** | Pin 20 | GP15 | Digital Signal |
| **Soil Sensor** | Pin 31 | GP26 (ADC0) | Analog Input |
| **VCC (All)** | Pin 36 | 3.3V | Power |
| **GND (All)** | Pin 38 | GND | Ground |

---

## 🧪 Testing Strategy
* **Unit Testing**: Validation of calculation logic (e.g., ADC raw values to % conversion) on the local host machine.
* **Hardware Validation**: Specialized scripts executed directly on the Pico via the "Run" command to verify component health.
* **Separation of Concerns**: The root-level `tests/` folder ensures a clean separation between testing suites and production-ready firmware.

---

## 📝 Quick Start
1. Flash the Pico W with the latest MicroPython .uf2 firmware.
2. Open the `/firmware` folder in VS Code and initialize the MicroPico project.
3. Update VS Code settings: `micropico.sync.auto: true`.
4. Run `docker-compose up -d` on the Raspberry Pi 4 to boot the infrastructure.
