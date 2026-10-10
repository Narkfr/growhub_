"""Un client MQTT ne porte qu'une seule session : les noms doivent être uniques.

Deux processus qui publient sous le même identifiant client se déconnectent
mutuellement en boucle (``session taken over`` dans le journal du broker) : le
cas s'est produit en vrai entre l'API et le worker, qui publient tous les deux
les identifiants d'appairage.
"""

import os

from telemetry.mqtt import MqttPublisher, process_client_id


def test_client_id_includes_the_process(monkeypatch):
    monkeypatch.setattr(os, "getpid", lambda: 0x2A)
    assert process_client_id("gh-prov").endswith("-2a")


def test_two_containers_do_not_share_a_client_id(monkeypatch):
    """Le PID vaut 1 dans chacun des deux conteneurs : l'hôte doit trancher."""
    monkeypatch.setattr(os, "getpid", lambda: 1)

    monkeypatch.setattr("socket.gethostname", lambda: "3f2a91c0d4e5")
    api = process_client_id("gh-prov")

    monkeypatch.setattr("socket.gethostname", lambda: "7b1e08a4c2f9")
    worker = process_client_id("gh-prov")

    assert api != worker


def test_publisher_defaults_are_distinct_per_call_site():
    """Le compte d'amorçage et les commandes ne publient pas sous le même nom."""
    assert MqttPublisher().client_id != MqttPublisher(client_id="gh-cmd").client_id


def test_publisher_keeps_its_client_id(monkeypatch):
    monkeypatch.setattr("socket.gethostname", lambda: "abcdef123456")
    monkeypatch.setattr(os, "getpid", lambda: 7)
    assert MqttPublisher(client_id="gh-prov").client_id == "gh-prov-abcdef12-7"


def test_shared_publisher_opens_a_session_once_per_use(monkeypatch):
    """Un publicateur par usage et par processus — jamais un par appel.

    La session reste ouverte et se reconnecte toute seule : en créer une à chaque
    requête faisait que chacune délogeait la précédente, sans fin.
    """
    from telemetry import mqtt

    opened = []

    class CountingPublisher:
        def __init__(self, client_id=None):
            opened.append(client_id)

    monkeypatch.setattr(mqtt, "_SHARED", {})
    monkeypatch.setattr(mqtt, "MqttPublisher", CountingPublisher)

    first = mqtt.shared_publisher("gh-cmd")
    assert mqtt.shared_publisher("gh-cmd") is first
    mqtt.shared_publisher("gh-prov")

    assert opened == ["gh-cmd", "gh-prov"]
