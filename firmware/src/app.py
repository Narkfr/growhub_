"""Contrôleur du Bourgeon : matériel, télémétrie, commandes et appairage.

Deux modes, décidés au démarrage par la présence du fichier d'identifiants :

* **appairage** (pas de ``creds.json``) — le boîtier se connecte avec le compte
  d'amorçage, s'annonce sur son topic de provisioning et attend ses identifiants
  définitifs ; l'écran affiche le code à saisir dans l'application ;
* **normal** — identifiants définitifs, télémétrie périodique, commandes.

Le boîtier ne décide jamais de son propriétaire : il transporte des mesures et
exécute des commandes, tout le contrôle d'accès vit côté serveur.
"""

import asyncio

import machine
from constants import (
    ALLOWED_ACTUATOR_ACTIONS,
    ALLOWED_CONFIG_ACTIONS,
    ALLOWED_SENSOR_ACTIONS,
    FW_VERSION,
    MIN_TELEMETRY_INTERVAL_SECONDS,
    MODEL,
    TELEMETRY_INTERVAL_SECONDS,
)
from src import identity, topics
from src.actuators.base import BaseActuator, ManualButton
from src.mqtt_manager import MqttManager
from src.network_manager import NetworkManager
from src.sensors.sensor_classes import SENSOR_CLASSES


class GrowHubController:
    def __init__(self, manifest, secrets, credentials_path=None):
        self.manifest = manifest
        self.secrets = secrets

        # Identité : provisionnée si le serveur l'a déjà enregistrée, sinon
        # dérivée du microcontrôleur.
        self.device_id = identity.resolve_device_id(secrets)
        self.pairing_code = secrets.get("PAIRING_CODE")

        # Identifiants : ceux de l'appairage réussi priment sur le compte
        # d'amorçage du fichier secrets.py.
        self.credentials_path = credentials_path or identity.CREDENTIALS_PATH
        stored = identity.load_credentials(self.credentials_path)
        if stored:
            self.credentials = stored
            self.pairing = False  # appairé : identifiants définitifs
        else:
            self.credentials = identity.credentials_from_secrets(secrets)
            self.pairing = True  # compte d'amorçage : appairage à faire

        self.wifi = NetworkManager(
            secrets.get("WIFI_SSID"), secrets.get("WIFI_PASSWORD")
        )
        self.mqtt = MqttManager(
            device_id=self.device_id,
            broker_ip=self.credentials["broker"],
            user=self.credentials["username"],
            password=self.credentials["password"],
            port=self.credentials["port"],
        )

        # Matériel
        self.sensors = {}
        self.actuators = {}
        self.buttons = []
        self._setup_hardware()

        # État applicatif
        self.telemetry_interval = TELEMETRY_INTERVAL_SECONDS
        self._sequence = 0

        self.mqtt.set_callback(self._on_message)

        # Écran (optionnel, déclaré dans le manifeste)
        self.display = None
        self._setup_display()

    # -- mise en place --------------------------------------------------------

    def _setup_hardware(self):
        for item in self.manifest["actuators"]:
            self.actuators[item["id"]] = BaseActuator(
                item["pin"], item["id"], item.get("active_low", True)
            )

        for item in self.manifest["sensors"]:
            cls = SENSOR_CLASSES.get(item["type"])
            if cls:
                args = {"pin_number": item["pin"], "sensor_id": item["id"]}
                if "calibration" in item:
                    args.update({"calibration": item["calibration"]})
                self.sensors[item["id"]] = cls(**args)

        for item in self.manifest["buttons"]:
            self.buttons.append(ManualButton(item["pin"], item["id"], item["target"]))

    def _setup_display(self):
        if "display" not in self.manifest:
            return
        from src.display import Display

        self.display = Display(self.manifest["display"])

    # -- payloiades ----------------------------------------------------------

    def _actuator_states(self):
        return {aid: act.human_state() for aid, act in self.actuators.items()}

    def _capabilities(self):
        """Ce que le boîtier sait faire, tel qu'annoncé sur le topic ``info``.

        Le serveur en dérive ses ``Capability`` : c'est le boîtier qui déclare
        ses capteurs et actionneurs, jamais l'utilisateur à la main.
        """
        return {
            "model": self.manifest.get("model", MODEL),
            "fw": FW_VERSION,
            "hw_id": self.device_id,
            "sensors": [{"name": sensor_id} for sensor_id in self.sensors],
            "actuators": [{"name": actuator_id} for actuator_id in self.actuators],
        }

    def _subscriptions(self):
        subscribed = topics.command_topics(self.device_id)
        if self.pairing:
            subscribed.append(topics.provision_credentials(self.device_id))
        return subscribed

    # -- réception -----------------------------------------------------------

    @staticmethod
    def _decode(payload):
        if isinstance(payload, (bytes, bytearray)):
            try:
                import ujson

                return ujson.loads(payload)
            except ValueError:
                return {}
        return payload if isinstance(payload, dict) else {}

    def _on_message(self, topic, msg):
        """Aiguillage des messages entrants, sans jamais lever d'exception."""
        try:
            name = topic.decode() if isinstance(topic, (bytes, bytearray)) else topic
            payload = self._decode(msg)

            if self.pairing and topics.is_provision_credentials(self.device_id, name):
                self._handle_credentials(payload)
                return

            category = topics.command_category(self.device_id, name)
            if category is None:
                return
            handler = getattr(self, f"_handle_{category}_command", None)
            if handler is not None:
                handler(payload)
        except Exception as e:
            print(f"Erreur dans le callback : {e}")

    def _ack(self, cmd_id, ok, error="", state=None):
        self.mqtt.publish(
            topics.ack(self.device_id),
            {"cmd_id": cmd_id, "ok": ok, "error": error, "state": state},
        )

    def _handle_actuators_command(self, payload):
        cmd_id = payload.get("cmd_id")
        action = str(payload.get("action", "")).lower()
        target_id = (payload.get("args") or {}).get("target")
        target = self.actuators.get(target_id)

        if action not in ALLOWED_ACTUATOR_ACTIONS or target is None:
            self._ack(cmd_id, False, error="actionneur ou action inconnus")
            return
        if not hasattr(target, action):
            self._ack(cmd_id, False, error="action non supportée")
            return

        getattr(target, action)()
        states = self._actuator_states()
        # L'état part en retained : un tableau de bord qui se reconnecte
        # retrouve l'état des actionneurs sans attendre la prochaine télémétrie.
        self.mqtt.publish(
            self.mqtt.publish(
                topics.state(self.device_id), {"actuators": states}, retain=True
            )
        )
        # Même forme que le topic state : le serveur peut l'appliquer tel quel.
        self._ack(cmd_id, True, state={"actuators": states})

    def _handle_sensors_command(self, payload):
        cmd_id = payload.get("cmd_id")
        action = str(payload.get("action", "")).lower()
        target_id = (payload.get("args") or {}).get("target")
        target = self.sensors.get(target_id)

        if action not in ALLOWED_SENSOR_ACTIONS or target is None:
            self._ack(cmd_id, False, error="capteur ou action inconnus")
            return

        reading = target.read()
        if reading is None:
            self._ack(cmd_id, False, error="lecture impossible")
            return

        self._sequence += 1
        self.mqtt.publish(
            topics.telemetry(self.device_id),
            {"seq": self._sequence, "sensors": {target_id: reading}},
        )
        self._ack(cmd_id, True, state={"sensors": {target_id: reading}})

    def _handle_config_command(self, payload):
        cmd_id = payload.get("cmd_id")
        action = str(payload.get("action", "")).lower()
        args = payload.get("args") or {}

        if action not in ALLOWED_CONFIG_ACTIONS:
            self._ack(cmd_id, False, error="action de configuration inconnue")
            return

        applied = {}
        for key, value in args.items():
            if key == "telemetry_interval":
                try:
                    interval = int(value)
                except (TypeError, ValueError):
                    self._ack(cmd_id, False, error="intervalle invalide")
                    return
                if interval < MIN_TELEMETRY_INTERVAL_SECONDS:
                    self._ack(
                        cmd_id,
                        False,
                        error=f"intervalle minimal {MIN_TELEMETRY_INTERVAL_SECONDS} s",
                    )
                    return
                self.telemetry_interval = interval
                applied[key] = interval
            else:
                self._ack(cmd_id, False, error=f"clé inconnue : {key}")
                return

        self.mqtt.publish(
            topics.state(self.device_id),
            {"config": {"telemetry_interval": self.telemetry_interval}},
            retain=True,
        )
        self._ack(cmd_id, True, state={"config": applied})

    def _handle_credentials(self, payload):
        """Identifiants définitifs reçus : on les écrit puis on redémarre.

        Le redémarrage évite de réécrire à chaud le client MQTT et les
        abonnements ; le fichier écrit est la seule source de vérité ensuite.
        """
        username = payload.get("username")
        password = payload.get("password")
        if not username or not password:
            print("Identifiants incomplets, ignorés.")
            return

        identity.save_credentials(
            username,
            password,
            payload.get("broker", self.mqtt.broker_ip),
            payload.get("port", self.mqtt.port),
            path=self.credentials_path,
        )
        print("Identifiants reçus : redémarrage du Bourgeon.")
        machine.reset()

    # -- boucles -------------------------------------------------------------

    async def _read_sensor(self, sensor, retries=3):
        """Lit un capteur, en réessayant de façon asynchrone sur ``None``."""
        for _ in range(retries):
            try:
                value = sensor.read()
            except Exception as e:
                print(f"Erreur de lecture capteur : {e}")
                value = None
            if value is not None:
                return value
            await asyncio.sleep(2)
        return None

    def _announce(self):
        """Annonce le boîtier au serveur (retained) après une connexion."""
        self.mqtt.publish(
            topics.info(self.device_id), self._capabilities(), retain=True
        )
        self.mqtt.publish(
            topics.state(self.device_id),
            {"actuators": self._actuator_states()},
            retain=True,
        )
        if self.pairing:
            self.mqtt.publish(
                topics.provision(self.device_id),
                {
                    "device_id": self.device_id,
                    "model": self.manifest.get("model", MODEL),
                    "fw": FW_VERSION,
                },
                retain=True,
            )

    async def _telemetry_task(self):
        while True:
            if self.wifi.wlan.isconnected() and self.mqtt.is_connected():
                self._sequence += 1
                data = {
                    "seq": self._sequence,
                    "sensors": {},
                    "actuators": self._actuator_states(),
                }
                for sensor_id, sensor in self.sensors.items():
                    reading = await self._read_sensor(sensor)
                    if reading is not None:
                        data["sensors"][sensor_id] = reading
                # Pas d'horodatage : le boîtier n'a pas d'horloge fiable, c'est
                # le serveur qui date à la réception.
                self.mqtt.publish(topics.telemetry(self.device_id), data)
            await asyncio.sleep(self.telemetry_interval)

    async def _listen_task(self):
        while True:
            if self.wifi.wlan.isconnected() and self.mqtt.is_connected():
                self.mqtt.check_msg()
            await asyncio.sleep(0.1)

    async def _button_task(self):
        """Lecture fréquente et non bloquante des boutons poussoirs."""
        while True:
            for btn in self.buttons:
                if btn.is_pressed():
                    target = self.actuators.get(btn.target_id)
                    if target:
                        target.toggle()
                        self.mqtt.publish(
                            topics.state(self.device_id),
                            {"actuators": self._actuator_states()},
                            retain=True,
                        )
                        await asyncio.sleep(0.3)
            await asyncio.sleep(0.05)

    async def _mqtt_keepalive(self):
        """Reconnecte le broker dès que le Wi-Fi revient."""
        while True:
            if self.wifi.wlan.isconnected() and not self.mqtt.is_connected():
                if await self.mqtt.connect(self._subscriptions()):
                    self._announce()
            await asyncio.sleep(10)

    async def _display_task(self):
        """Affiche l'appairage, puis la télémétrie, sur l'écran OLED."""
        if self.display is None:
            return
        while True:
            try:
                if self.pairing:
                    self._render_pairing()
                else:
                    await self._render_telemetry()
            except Exception as e:
                print(f"Erreur d'affichage : {e}")
            await asyncio.sleep(2)

    def _render_pairing(self):
        display = self.display
        if display is None:
            return
        display.clear()
        display.text("BOURGEON", 0, 0)
        display.text("Code : " + str(self.pairing_code or "----"), 0, 20)
        display.text(self.device_id, 0, 40)
        display.show()

    async def _render_telemetry(self):
        if self.display is None:
            return
        temperature = None
        humidity = None
        for sensor in self.sensors.values():
            data = await self._read_sensor(sensor, retries=1)
            if not data:
                continue
            if "temperature" in data:
                temperature = data["temperature"]["value"]
                humidity = data.get("humidity", {}).get("value")

        self.display.clear()
        self.display.text("BOURGEON", 0, 0)
        if temperature is not None and humidity is not None:
            self.display.text(f"Temp: {temperature} C", 0, 25)
            self.display.text(f"Hum: {humidity}%", 0, 45)
        else:
            self.display.text("Erreur Capteur", 0, 25)
        self.display.show()

    async def run(self):
        """Point d'entrée de la boucle asyncio.

        Toutes les tâches démarrent immédiatement : l'écran et les boutons
        continuent de fonctionner même sans Wi-Fi ni broker.
        """
        await asyncio.gather(
            self._telemetry_task(),
            self._listen_task(),
            self._button_task(),
            self._display_task(),
            self.wifi.keep_connected(),
            self._mqtt_keepalive(),
        )
