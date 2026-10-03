# GrowHub — Tooling Reference

This page lists every tool used in the GrowHub project and explains what each
one is for, grouped by stage of the workflow.

---

## 1. Flashing & OS images

### Rufus
Writes the Raspberry Pi OS image to the gateway's SD card as a bootable drive.
Rufus runs on Windows; on macOS/Linux the official
[Raspberry Pi Imager](https://www.raspberrypi.com/software/) or
[balenaEtcher](https://etcher.balena.io/) does the same job.

Used once when setting up the Raspberry Pi 4 gateway.

### MicroPython firmware (`.uf2`)
The Pico W runs MicroPython. The firmware is a single `.uf2` file flashed by
holding the BOOTSEL button while plugging the board in (it mounts as a USB
drive) and copying the file over — no extra tool needed.

---

## 2. Development environment

### VS Code + MicroPico
The firmware IDE. The **MicroPico** extension points `projectRoot` at
`firmware/` and provides sync-on-save: every save uploads the changed file to
the Pico's flash automatically.

### VS Code Remote-SSH
Opens a VS Code session directly on the Raspberry Pi 4 over SSH, so gateway
code is edited and run where it deploys.

### Python 3.11+ (venv)
The gateway scripts (`logic_engine.py`, `telemetry_logger.py`, `sync_itk.py`,
`init_db.py`, and the `gateway/api/` live API) are plain Python. Dependencies
are kept in a virtual environment: `flask`, `influxdb-client`, `paho-mqtt`,
`python-dotenv`, `psycopg2-binary`, `apscheduler`, `rich`.

### git + gh (GitHub CLI)
Version control and GitHub automation (PRs, issues, reviews). CI runs on
GitHub Actions.

### ruff
Python linter and formatter. `ruff check .` (lint) and `ruff format .`
(format) — both enforced in CI.

### pytest
The test runner. `python -m pytest -q` runs the unit test suite (`tests/`),
with MicroPython and third-party modules mocked on the host.

---

## 3. Gateway services (Docker)

### Docker & Docker Compose
Run the whole gateway stack as reproducible containers. `docker compose up -d`
in `gateway/` boots Mosquitto, InfluxDB, PostgreSQL and Adminer from
`docker-compose.yml`.

### Eclipse Mosquitto
The MQTT broker. Devices publish telemetry and subscribe to actuator commands
through it. The `mosquitto_sub` / `mosquitto_pub` clients are handy for
debugging topics from the shell.

### PostgreSQL
Relational database. Stores the technical itineraries (ITKs), their phases and
the device registry — the "planning" side of the system.

### InfluxDB
Time-series database. Stores sensor telemetry and actuator state history — the
"measurement" side of the system.

### Adminer
A lightweight web UI (port 8080) to inspect and query the PostgreSQL database
from the browser.

### Grafana *(planned)*
Visualization dashboards over InfluxDB telemetry. Not yet wired.

---

## 4. Web interface

### Next.js + Tailwind
The real-time dashboard front-end (`gateway/frontend/`). A single page that
opens a Server-Sent Events stream to the API and renders live sensor readings
and actuator states, with a polling fallback when the stream drops. Built
with Next.js 15 (App Router), TypeScript and Tailwind CSS.

### Flask
The real-time API (`gateway/api/`). An MQTT subscriber (paho-mqtt) that keeps
the latest state of every device in a thread-safe in-memory registry and
serves it as JSON (`/api/state`) and Server-Sent Events (`/api/stream`).

### vitest
The frontend's test runner (pure formatting/label helpers in
`src/lib/format.test.ts`).

---

## 5. Repo helper tools

These live in the `tools/` directory (plus one in `gateway/`).

| Tool | Runs on | Purpose |
| :--- | :--- | :--- |
| `tools/hardware/soil_calibration.py` | Pico W | Measures the soil sensor's dry (air) and wet (water) ADC values so you can fill `calibration` in `firmware/manifest.py`. |
| `tools/hardware/check_minigreenhouse_hardware.py` | Pico W | Reads both sensors repeatedly to validate wiring and calibration in one go. |
| `tools/gateway/mqtt.py` | Gateway / host | Minimal MQTT publish/subscribe smoke test to confirm broker credentials and connectivity. |
| `gateway/pretty_subscriber.py` | Gateway / host | Live terminal dashboard (`rich`) showing the latest telemetry and actuator states over MQTT. |
