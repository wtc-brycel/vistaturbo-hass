import sys
import types


class FakeClient:
    def __init__(self, *args, **kwargs):
        self.published = []
        self.subscriptions = []
        self.on_connect = None
        self.on_disconnect = None
        self.on_message = None
        self.tls = None
        self.max_inflight_messages = None
        self.max_queued_messages = None

    def username_pw_set(self, *args, **kwargs):
        pass

    def reconnect_delay_set(self, *args, **kwargs):
        pass

    def will_set(self, *args, **kwargs):
        pass

    def tls_set(self, *args, **kwargs):
        self.tls = (args, kwargs)

    def max_inflight_messages_set(self, value):
        self.max_inflight_messages = value

    def max_queued_messages_set(self, value):
        self.max_queued_messages = value

    def connect_async(self, *args, **kwargs):
        pass

    def loop_start(self):
        pass

    def loop_stop(self):
        pass

    def disconnect(self):
        pass

    def publish(self, topic, payload=None, qos=0, retain=False):
        self.published.append((topic, payload, qos, retain))

    def subscribe(self, topic, qos=0):
        self.subscriptions.append((topic, qos))


def install_fake_paho() -> None:
    client = types.ModuleType("paho.mqtt.client")
    client.Client = FakeClient
    client.CallbackAPIVersion = types.SimpleNamespace(VERSION2=2)
    client.MQTTv311 = 4

    mqtt = types.ModuleType("paho.mqtt")
    mqtt.client = client
    paho = types.ModuleType("paho")
    paho.mqtt = mqtt

    sys.modules.setdefault("paho", paho)
    sys.modules.setdefault("paho.mqtt", mqtt)
    sys.modules.setdefault("paho.mqtt.client", client)
