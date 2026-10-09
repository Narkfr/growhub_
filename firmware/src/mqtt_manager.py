import ujson
from lib.umqtt.simple import MQTTClient


class MqttManager:
    """Handles MQTT connection and data publishing."""

    def __init__(
        self, client_id, broker_ip, user, password, port=1883, connect_timeout=5
    ):
        self.client = MQTTClient(
            client_id=client_id,
            server=broker_ip,
            user=user,
            password=password,
            port=port,
            keepalive=60,
        )
        self.broker_ip = broker_ip
        self.connect_timeout = connect_timeout
        self.connected = False
        self.subscriptions = [
            f"{client_id}/actuators/+/action",
            f"{client_id}/sensors/+/action",
        ]
        self.status_topic = f"{client_id}/status"

    def set_callback(self, callback_func):
        self.client.set_callback(callback_func)

    def is_connected(self):
        return self.connected

    def disconnect(self):
        """Close the current socket (if any) and mark disconnected."""
        try:
            self.client.disconnect()
        except Exception:
            pass
        self.connected = False

    async def connect(self):
        """Connect to the broker and (re)subscribe to the command topics."""
        self.disconnect()
        try:
            # Last Will: the broker publishes this if we drop unexpectedly.
            self.client.set_last_will(self.status_topic, b"offline", retain=True)
            self.client.connect(timeout=self.connect_timeout)
            for topic in self.subscriptions:
                self.client.subscribe(topic)
            self.connected = True
            # Announce presence (retained so the gateway sees current state).
            self.client.publish(self.status_topic, b"online", retain=True)
            print(
                f"Connected to MQTT Broker at {self.broker_ip} and "
                f"subscribed to {self.client.client_id}"
            )
            return True
        except Exception as e:
            self.connected = False
            print(f"Failed to connect to MQTT: {e}")
            return False

    def check_msg(self):
        """Pump incoming MQTT messages; mark disconnected on socket errors."""
        try:
            self.client.check_msg()
        except Exception:
            self.connected = False

    def publish(self, topic, data, retain=False, qos=0):
        """Publish a dictionary as a JSON string.

        QoS stays 0: umqtt.simple's QoS 1 publish blocks waiting for PUBACK,
        which would stall the event loop. Use retain=True for state that must
        survive on the broker (e.g. actuator state).
        """
        try:
            msg = ujson.dumps(data)
            self.client.publish(topic, msg, retain=retain, qos=qos)
        except Exception as e:
            self.connected = False
            print(f"Failed to publish: {e}")
