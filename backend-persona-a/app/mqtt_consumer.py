"""Consumidor MQTT: sat/forest/<NODE>/telemetry -> cola -> Engine (hilo aparte)."""
from __future__ import annotations
import json, logging, queue, threading
import paho.mqtt.client as mqtt

log = logging.getLogger("sat.mqtt")


def make_client():
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)  # paho-mqtt 2.x
    except AttributeError:
        return mqtt.Client()  # paho-mqtt 1.x


class MqttConsumer:
    def __init__(self, settings, engine):
        self.s, self.engine = settings, engine
        self.q = queue.Queue(maxsize=1000)
        self.connected = False
        self.stop_evt = threading.Event()
        self.client = make_client()
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.reconnect_delay_set(1, 15)

    def _on_connect(self, client, userdata, flags, rc, *args):
        self.connected = True
        client.subscribe(self.s.mqtt_topic, qos=1)  # se re-suscribe en cada reconexion
        log.info("MQTT conectado, suscrito a %s", self.s.mqtt_topic)

    def _on_disconnect(self, client, userdata, *args):
        self.connected = False
        log.warning("MQTT desconectado")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload)
        except ValueError:
            self.engine.stats["rejected"] += 1
            return
        parts = msg.topic.split("/")
        if isinstance(payload, dict) and len(parts) >= 3 and payload.get("node_id") != parts[2]:
            self.engine.stats["rejected"] += 1
            self.engine.stats["last_error"] = "node_id no coincide con el topico"
            return
        try:
            self.q.put_nowait(payload)
        except queue.Full:
            self.engine.stats["rejected"] += 1

    def _worker(self):
        while not self.stop_evt.is_set():
            try:
                payload = self.q.get(timeout=1)
            except queue.Empty:
                continue
            try:
                self.engine.process_telemetry(payload)
            except ValueError as e:
                log.info("Lectura descartada: %s", e)
            except Exception:
                log.exception("error procesando telemetria")

    def start(self):
        threading.Thread(target=self._worker, daemon=True, name="telemetry-worker").start()
        self.client.connect_async(self.s.mqtt_host, self.s.mqtt_port)  # no falla si no hay broker
        self.client.loop_start()

    def stop(self):
        self.stop_evt.set()
        self.client.loop_stop()

    def publish_control(self, payload):
        try:
            self.client.publish(self.s.mqtt_control_topic, json.dumps(payload), qos=1)
        except Exception as e:
            log.warning("no se pudo publicar control: %s", e)
