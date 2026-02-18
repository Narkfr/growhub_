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

    def set_callback(self, callback_func):
        self.client.set_callback(callback_func)

    async def connect(self):
        """Connect to the MQTT broker."""
        try:
            self.client.connect()
            # TODO: Consider subscribing to something related to config.json
            # in the future for dynamic updates
            self.client.subscribe(f"{self.client.client_id}/actuators/+/action")
            self.client.subscribe(f"{self.client.client_id}/sensors/+/action")
            print(
                f"Connected to MQTT Broker at {self.broker_ip} and subscribed \
                    to {self.client.client_id}"
            )
            return True
        except Exception as e:
            print(f"Failed to connect to MQTT: {e}")
            return False

    def check_msg(self):
        self.client.check_msg()

    def publish(self, topic, data):
        """Publish a dictionary as a JSON string."""
        try:
            msg = ujson.dumps(data)
            self.client.publish(topic, msg)
        except Exception as e:
            print(f"Failed to publish: {e}")
