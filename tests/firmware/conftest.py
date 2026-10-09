"""Mocks des modules MicroPython, partagés par tous les tests du firmware.

Ils vivent ici et non dans chaque fichier de test : pytest importe *tous* les
modules de test avant d'en exécuter un seul, donc le dernier module importé
écrasait les mocks des autres (un ``ujson`` incomplet faisait échouer des dizaines
de tests sans rapport).
"""

import binascii
import importlib.util
import json as _json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

_FIRMWARE = Path(__file__).resolve().parents[2] / "firmware"
if str(_FIRMWARE) not in sys.path:
    sys.path.insert(0, str(_FIRMWARE))

# --- Matériel et réseau ------------------------------------------------------

_machine = MagicMock()
_machine.unique_id.return_value = b"\x01\x02\x03\x04\x05\x06\x07\x08"
sys.modules["machine"] = _machine

_ubinascii = types.ModuleType("ubinascii")
_ubinascii.hexlify = binascii.hexlify
sys.modules["ubinascii"] = _ubinascii

# ujson complet : le firmware lit (load) et écrit (dump) les identifiants.
_ujson = types.ModuleType("ujson")
_ujson.dumps = _json.dumps
_ujson.loads = _json.loads
_ujson.load = _json.load
_ujson.dump = _json.dump
sys.modules["ujson"] = _ujson

sys.modules["dht"] = MagicMock()

_network = MagicMock()
_network.STA_IF = 0
sys.modules["network"] = _network


async def _noop(_seconds):
    return None


_uasyncio = types.ModuleType("uasyncio")
_uasyncio.sleep = _noop
sys.modules["uasyncio"] = _uasyncio

_lib = types.ModuleType("lib")
_lib.__path__ = []
_umqtt = types.ModuleType("lib.umqtt")
_umqtt.__path__ = []
_simple = types.ModuleType("lib.umqtt.simple")
_simple.MQTTClient = MagicMock()
_simple.MQTTException = type("MQTTException", (Exception,), {})
sys.modules["lib"] = _lib
sys.modules["lib.umqtt"] = _umqtt
sys.modules["lib.umqtt.simple"] = _simple


# --- Doublures matérielles utilisées par app.py ------------------------------


class FakeActuator:
    def __init__(self, pin, actuator_id, active_low=True):
        self.pin = pin
        self.id = actuator_id
        self.active_low = active_low
        self.on = MagicMock()
        self.off = MagicMock()
        self.toggle = MagicMock()
        self.is_on = MagicMock(return_value=False)
        self.human_state = MagicMock(return_value="OFF")


class FakeButton:
    def __init__(self, pin, button_id, target_id):
        self.pin = pin
        self.id = button_id
        self.target_id = target_id
        self.is_pressed = MagicMock(return_value=False)


class FakeSensor:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.read = MagicMock(return_value={"v": 1})


class FakeNetworkManager:
    def __init__(self, ssid, password):
        self.ssid = ssid
        self.password = password
        self.wlan = MagicMock()


_act_base = types.ModuleType("src.actuators.base")
_act_base.BaseActuator = FakeActuator
_act_base.ManualButton = FakeButton
sys.modules["src.actuators.base"] = _act_base

_mqtt_mod = types.ModuleType("src.mqtt_manager")
_mqtt_mod.MqttManager = MagicMock
sys.modules["src.mqtt_manager"] = _mqtt_mod

_net_mod = types.ModuleType("src.network_manager")
_net_mod.NetworkManager = FakeNetworkManager
sys.modules["src.network_manager"] = _net_mod

_sensor_classes = types.ModuleType("src.sensors.sensor_classes")
_sensor_classes.SENSOR_CLASSES = {"csmsv2": FakeSensor, "dht11": FakeSensor}
sys.modules["src.sensors.sensor_classes"] = _sensor_classes

# Le vrai ScreenLayout est utilisé (c'est de la logique pure) : seule la dalle
# physique est remplacée. Il est chargé par chemin pour ne pas importer le paquet
# `src.display`, qui tirerait `lib.ssd1306` et `machine`.
_SCREEN_PATH = _FIRMWARE / "src" / "display" / "screen.py"
_screen_spec = importlib.util.spec_from_file_location("growhub_screen", _SCREEN_PATH)
_screen_module = importlib.util.module_from_spec(_screen_spec)
_screen_spec.loader.exec_module(_screen_module)

_display = types.ModuleType("src.display")
# Une instance (et non la classe MagicMock) : les tests l'utilisent comme
# fabrique, ce qui permet Display.reset_mock() et Display.return_value.
_display.Display = MagicMock()
_display.ScreenField = _screen_module.ScreenField
_display.ScreenLayout = _screen_module.ScreenLayout
sys.modules["src.display"] = _display
