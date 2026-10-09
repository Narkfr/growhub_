"""Connexion MQTT du Bourgeon (contrat growhub/v1).

Le client MQTT s'identifie par l'identifiant du boîtier lui-même : côté broker,
les ACL sont écrites avec le motif ``%u``, donc c'est ce nom d'utilisateur qui
délimite ce que l'appareil peut lire et écrire.
"""

import ujson
from lib.umqtt.simple import MQTTClient
from src import topics


class MqttManager:
    """Connexion, abonnements et publication JSON."""

    def __init__(
        self, device_id, broker_ip, user, password, port=1883, connect_timeout=5
    ):
        self.device_id = device_id
        self.broker_ip = broker_ip
        self.port = port
        self.connect_timeout = connect_timeout
        self.client = MQTTClient(
            client_id=device_id,
            server=broker_ip,
            user=user,
            password=password,
            port=port,
            keepalive=60,
        )
        self.connected = False
        self.status_topic = topics.status(device_id)

    def set_callback(self, callback_func):
        self.client.set_callback(callback_func)

    def is_connected(self):
        return self.connected

    def disconnect(self):
        """Ferme la socket courante (si elle existe) et se marque déconnecté."""
        try:
            self.client.disconnect()
        except Exception:
            pass
        self.connected = False

    async def connect(self, subscriptions=None):
        """Se connecte, s'abonne aux topics de commande, s'annonce en ligne.

        Le testament (last will) est publié par le broker si la liaison tombe :
        c'est lui qui rend l'état « hors ligne » fiable côté serveur, sans
        dépendre du bon vouloir du boîtier.
        """
        self.disconnect()
        try:
            self.client.set_last_will(self.status_topic, b"offline", retain=True)
            self.client.connect(timeout=self.connect_timeout)
            for topic in subscriptions or topics.command_topics(self.device_id):
                self.client.subscribe(topic)
            self.connected = True
            self.client.publish(self.status_topic, b"online", retain=True)
            print(
                f"Connecté au broker MQTT {self.broker_ip} en tant que {self.device_id}"
            )
            return True
        except Exception as e:
            self.connected = False
            print(f"Échec de connexion MQTT : {e}")
            return False

    def check_msg(self):
        """Vide la file des messages entrants ; erreur socket = déconnecté."""
        try:
            self.client.check_msg()
        except Exception:
            self.connected = False

    def publish(self, topic, data, retain=False, qos=0):
        """Publie un dictionnaire en JSON (ou une charge utile déjà encodée).

        Le QoS reste à 0 : en QoS 1, ``umqtt.simple`` bloque en attendant le
        PUBACK, ce qui figerait la boucle d'événements. ``retain=True`` réserve
        aux états qui doivent survivre au boîtier (info, état des actionneurs).
        """
        try:
            payload = data if isinstance(data, (bytes, str)) else ujson.dumps(data)
            self.client.publish(topic, payload, retain=retain, qos=qos)
            return True
        except Exception as e:
            self.connected = False
            print(f"Échec de publication : {e}")
            return False
