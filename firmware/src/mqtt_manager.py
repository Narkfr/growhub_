import ujson
from lib.umqtt.simple import MQTTClient


class MqttManager:
    """Handles MQTT connection and data publishing."""

    def __init__(self, client_id, broker_ip, user, password, port=1883):
        self.client = MQTTClient(
            client_id=client_id,
            server=broker_ip,
            user=user,
            password=password,
            port=port,
            keepalive=60,
        )
        self.broker_ip = broker_ip
        self.connected = False
        self.subscriptions = [
            f"{client_id}/actuators/+/action",
            f"{client_id}/sensors/+/action",
        ]

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
            self.client.connect()
            for topic in self.subscriptions:
                self.client.subscribe(topic)
            self.connected = True
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

    def publish(self, topic, data):
        """Publish a dictionary as a JSON string."""
        try:
            msg = ujson.dumps(data)
            self.client.publish(topic, msg)
        except Exception as e:
            self.connected = False
            print(f"Failed to publish: {e}")
