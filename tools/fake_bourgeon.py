#!/usr/bin/env python3
"""Bourgeon simulé : appairage puis télémétrie, sans matériel.

Rejoue ce que fait le firmware au premier boot (jalon M5) pour éprouver la
chaîne complète serveur ↔ broker ↔ appareil :

1. connexion au broker avec le compte d'amorçage (``boot-<device_id>``) ;
2. publication retained de ``info``, ``state`` et de l'annonce d'appairage sur
   ``growhub/v1/provision/<device_id>``, puis abonnement à ``…/creds`` ;
3. à la réception des identifiants définitifs, reconnexion sous l'identité de
   l'appareil (``<device_id>``) et publication de ``--frames`` trames de
   télémétrie ``{seq, sensors, actuators}`` — sans horodatage, c'est le serveur
   qui date à la réception.

Usage (depuis le conteneur backend, ou depuis l'hôte avec la même version de
paho) ::

    python gateway/backend/manage.py provision_device ghb-dead01 \\
        --secrets-path /tmp/dryrun_secrets.py

    python tools/fake_bourgeon.py --secrets /tmp/dryrun_secrets.py \\
        --frames 5 --creds-out /tmp/dryrun_creds.json

Pendant qu'il attend ses identifiants, il faut racheter le code d'appairage
(``POST /api/v1/devices/claims/redeem``) puis demander la livraison des
identifiants (``POST /api/v1/devices/<pk>/provision``) — c'est ce que fait
l'application. Code de retour 0 si l'appairage et toutes les trames sont passés.
"""

from __future__ import annotations

import argparse
import ast
import json
import pathlib
import re
import sys
import threading
import time

import paho.mqtt.client as mqtt

ROOT = "growhub/v1"
SENSORS = {
    "ClimateSensor": {
        "temperature": {"value": 21.5, "unit": "celsius"},
        "humidity": {"value": 55.0, "unit": "percent"},
    },
    "SoilSensor": {"moisture": {"value": 42.4, "unit": "percent"}},
}
ACTUATORS = {"WaterPump": "OFF", "GrowLamp": "OFF"}


def log(message):
    print(f"bourgeon: {message}", flush=True)


def read_secrets(path):
    """Lit le ``secrets.py`` écrit par ``provision_device`` sans l'exécuter."""
    text = pathlib.Path(path).read_text(encoding="utf-8")
    match = re.search(r"secrets\s*=\s*(\{.*\})", text, re.DOTALL)
    if match is None:
        raise SystemExit(f"{path} ne contient pas de dictionnaire `secrets`")
    return ast.literal_eval(match.group(1))


def new_client(client_id, username=None, password=None):
    client = mqtt.Client(
        client_id=client_id,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
    )
    if username:
        client.username_pw_set(username, password)
    return client


def capabilities(device_id, model, firmware):
    return {
        "model": model,
        "fw": firmware,
        "hw_id": device_id,
        "sensors": [{"name": name} for name in SENSORS],
        "actuators": [{"name": name} for name in ACTUATORS],
    }


def pair(args, secrets):
    """Étape 1 : compte d'amorçage, annonce retained, attente des identifiants."""
    device_id = args.device_id or secrets["DEVICE_ID"]
    received = {}

    client = new_client(
        f"fake-{device_id}",
        secrets["MQTT_USER"],
        secrets["MQTT_PASSWORD"],
    )

    def on_connect(client, userdata, flags, rc):
        if rc != 0:
            log(f"connexion refusée par le broker (rc={rc})")
            return
        log(f"connecté au broker avec le compte d'amorçage {secrets['MQTT_USER']}")
        client.publish(
            f"{ROOT}/{device_id}/info",
            json.dumps(capabilities(device_id, args.model, args.firmware)),
            retain=True,
        )
        client.publish(
            f"{ROOT}/{device_id}/state",
            json.dumps({"actuators": ACTUATORS}),
            retain=True,
        )
        client.publish(
            f"{ROOT}/provision/{device_id}",
            json.dumps(
                {
                    "device_id": device_id,
                    "model": args.model,
                    "fw": args.firmware,
                }
            ),
            retain=True,
        )
        client.subscribe(f"{ROOT}/provision/{device_id}/creds", qos=1)
        log(
            "annonce retained publiée sur "
            f"{ROOT}/provision/{device_id}, en attente des identifiants"
        )

    def on_message(client, userdata, message):
        payload = json.loads(message.payload or b"{}")
        if payload.get("username") and payload.get("password"):
            received.update(payload)
            log("identifiants reçus, bascule sur le compte de l'appareil")
            client.disconnect()

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(args.broker, args.port, keepalive=30)
    client.loop_start()

    deadline = time.monotonic() + args.timeout
    while not received and time.monotonic() < deadline:
        time.sleep(0.5)
    client.loop_stop()
    client.disconnect()

    if not received:
        log(f"aucun identifiant reçu en {args.timeout} s")
        return device_id, None

    if args.creds_out:
        pathlib.Path(args.creds_out).write_text(
            json.dumps(
                {
                    "username": received["username"],
                    "password": received["password"],
                    "broker": args.broker,
                    "port": args.port,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        log(f"creds.json écrit dans {args.creds_out}")
    return device_id, received


def publish_telemetry(args, device_id, creds):
    """Étape 2 : le boîtier repart sous son identité et publie ses mesures.

    Comme le firmware, il n'émet **que** lorsqu'il est connecté : juste après la
    livraison des identifiants, le broker peut encore ignorer le nouveau compte
    (le temps qu'il relise son fichier de mots de passe) et un refus de
    publication est silencieux en MQTT 3.1.1 — les trames partiraient dans le
    vide sans que personne ne le voie.
    """
    connected = threading.Event()

    client = new_client(device_id, creds["username"], creds["password"])
    client.reconnect_delay_set(min_delay=1, max_delay=5)

    def on_connect(client, userdata, flags, rc):
        if rc != 0:
            log(f"connexion refusée avec les identifiants définitifs (rc={rc})")
            return
        connected.set()
        log(f"connecté sous l'identité {device_id}")
        client.publish(
            f"{ROOT}/{device_id}/info",
            json.dumps(capabilities(device_id, args.model, args.firmware)),
            retain=True,
        )
        client.publish(
            f"{ROOT}/{device_id}/state",
            json.dumps({"actuators": ACTUATORS}),
            retain=True,
        )
        client.publish(f"{ROOT}/{device_id}/status", "online", retain=True)

    def on_disconnect(client, userdata, rc):
        connected.clear()

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.connect(args.broker, args.port, keepalive=30)
    client.loop_start()

    if not connected.wait(args.connect_timeout):
        log(
            f"pas de connexion avec les identifiants définitifs en "
            f"{args.connect_timeout:g} s (le broker a-t-il relu ses comptes ?)"
        )
        client.loop_stop()
        return 0

    published = 0
    for sequence in range(1, args.frames + 1):
        if not connected.wait(args.connect_timeout):
            log("déconnecté en cours de route, arrêt")
            break
        payload = {"seq": sequence, "sensors": SENSORS, "actuators": ACTUATORS}
        payload["sensors"]["ClimateSensor"]["temperature"]["value"] = round(
            21.0 + sequence / 10, 1
        )
        client.publish(f"{ROOT}/{device_id}/telemetry", json.dumps(payload))
        published += 1
        log(f"trame {sequence}/{args.frames} publiée")
        time.sleep(args.interval)

    client.publish(f"{ROOT}/{device_id}/status", "offline", retain=True)
    time.sleep(0.5)
    client.loop_stop()
    client.disconnect()
    return published


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--secrets", required=True, help="secrets.py du boîtier")
    parser.add_argument("--device-id", help="forcer l'identifiant (défaut : secrets)")
    parser.add_argument("--broker", help="défaut : MQTT_BROKER des secrets")
    parser.add_argument("--port", type=int, help="défaut : MQTT_PORT des secrets")
    parser.add_argument("--frames", type=int, default=5, help="trames à publier")
    parser.add_argument("--interval", type=float, default=1.0, help="secondes")
    parser.add_argument(
        "--timeout", type=float, default=120.0, help="attente des identifiants"
    )
    parser.add_argument(
        "--connect-timeout",
        type=float,
        default=30.0,
        help="attente d'une connexion acceptée par le broker",
    )
    parser.add_argument("--creds-out", help="écrire les identifiants reçus ici")
    parser.add_argument("--model", default="Bourgeon V1 (simulé)")
    parser.add_argument("--firmware", default="simule")
    args = parser.parse_args(argv)

    secrets = read_secrets(args.secrets)
    args.broker = args.broker or secrets["MQTT_BROKER"]
    args.port = args.port or int(secrets["MQTT_PORT"])

    device_id, creds = pair(args, secrets)
    if creds is None:
        return 1

    published = publish_telemetry(args, device_id, creds)
    if published != args.frames:
        log(f"{published}/{args.frames} trames publiées")
        return 1
    log(f"terminé : appairé et {published} trames publiées")
    return 0


if __name__ == "__main__":
    sys.exit(main())
