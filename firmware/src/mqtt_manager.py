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

    async def connect(self):
        """Connect to the MQTT broker."""
        try:
            self.client.connect()
            print(f"Connected to MQTT Broker at {self.broker_ip}")
            return True
        except Exception as e:
            print(f"Failed to connect to MQTT: {e}")
            return False

    def publish(self, topic, data):
        """Publish a dictionary as a JSON string."""
        try:
            msg = ujson.dumps(data)
            self.client.publish(topic, msg)
        except Exception as e:
            print(f"Failed to publish: {e}")
