# 🌿 GrowHub — Smart Greenhouse

An automated monitoring and control system for indoor cultivation. This project leverages a modern IoT architecture with a distributed Edge-to-Gateway approach, focused on reliability and data persistence.

---

## 🚀 System Architecture

| Layer | Technology | Role |
| :--- | :--- | :--- |
| **Edge Device** | Raspberry Pi Pico W | Sensor data collection (MicroPython) and actuator control. |
| **Connectivity** | MQTT over Wi-Fi | Lightweight pub/sub protocol for JSON data transport. |
| **Gateway Hub** | Raspberry Pi 4 (Docker) | MQTT Broker (Mosquitto), Time-series DB (InfluxDB), and Logic Bridge. |
| **Interface** | Next.js / Tailwind + Flask | Real-time dashboard (live telemetry + actuator states) over REST/SSE. |

---

## 📂 Project Structure (Clean Monorepo)

```text
growhub/
├── firmware/              # Embedded MicroPython source
│   ├── src/               # Core logic: sensors/, actuators/, managers
│   ├── lib/               # Bundled MicroPython libraries (umqtt)
│   ├── main.py            # Entry point (asyncio loop)
│   ├── manifest.py        # Hardware + calibration configuration
│   ├── constants.py       # Allowed actions / shared constants
│   ├── boot.py            # Runs at power-on (currently empty)
│   └── secrets.example.py # Credentials template (copy to secrets.py)
├── gateway/               # Server-side infrastructure (RPi 4)
│   ├── api/               # Flask real-time API (REST + SSE over MQTT)
│   ├── frontend/          # Next.js + Tailwind live dashboard
│   ├── mosquitto/         # MQTT Broker configuration + runtime data
│   ├── itk/               # Technical itinerary (ITK) JSON definitions
│   ├── logic_engine.py    # Automation / decision engine
│   ├── telemetry_logger.py# MQTT -> InfluxDB bridge
│   ├── sync_itk.py        # ITK JSON -> PostgreSQL sync
│   ├── init_db.py         # PostgreSQL schema initialization
│   └── docker-compose.yml # Docker service orchestration
├── tools/                 # Dev + hardware helpers
├── tests/                 # Unit tests (sensors + actuators, mocked HW)
├── docs/                  # Setup and build documentation
└── .gitignore             # Local and sensitive file exclusions
```

---

## 📚 Documentation

- [Tooling reference](docs/tooling.md) — the full list of tools used in the project and what each one is for.
- [Gateway setup guide](docs/gateway_setup.md) — how to deploy the Dockerized gateway stack.

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
5. Start the live dashboard (API + frontend) — see
   [Gateway setup guide](docs/gateway_setup.md) for the native systemd
   deployment used by the PoC.

---

## 🗺️ Roadmap / Known limitations

- **Temperature control**: `temp_min` / `temp_max` are defined in the ITK
  (`gateway/itk/*.json`) but not yet acted upon — there is no ventilation or
  heating actuator wired yet. Temperature is recorded as telemetry only.
- **Dashboard**: the live telemetry dashboard (`gateway/api` + `gateway/frontend`)
  is implemented and shows real-time sensor readings and actuator states.
  Historical charts over InfluxDB are not wired yet.
- **TLS**: MQTT runs plaintext on the local network; TLS is deferred (see
  `docs/gateway_setup.md`).
