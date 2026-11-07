"""Simulador de 3 nodos (CHI-01..03). Publica en MQTT como si vinieran de un gateway.
NO es una red LoRaWAN fisica: es telemetria sintetica marcada con simulated=true."""
import argparse, json, random, threading, time
from datetime import datetime, timezone
import paho.mqtt.client as mqtt

NODES = {"CHI-01": (-16.39, -61.05), "CHI-02": (-16.75, -60.70), "CHI-03": (-17.20, -61.40)}
# (temp C, humedad %, humo 0..1) por escenario; CHI-02 queda siempre en precaucion
PROFILES = {
    "normal":   {"CHI-01": (29, 55, .10), "CHI-02": (41, 30, .35), "CHI-03": (29, 55, .10)},
    "seco":     {"CHI-01": (41, 19, .10), "CHI-02": (41, 30, .35), "CHI-03": (29, 55, .10)},
    "incendio": {"CHI-01": (42, 18, .85), "CHI-02": (41, 30, .35), "CHI-03": (29, 55, .10)},
}
state = {"scenario": "normal"}


def make_client():
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except AttributeError:
        return mqtt.Client()


def reading(node):
    t, h, s = PROFILES[state["scenario"]][node]
    return {"temperature_c": round(t + random.uniform(-.4, .4), 1),
            "humidity_pct": int(round(h + random.uniform(-1, 1))),
            "smoke_index": round(min(1, max(0, s + random.uniform(-.02, .02))), 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--interval", type=float, default=5)
    ap.add_argument("--scenario", default="normal", choices=list(PROFILES))
    ap.add_argument("--no-input", action="store_true")
    a = ap.parse_args()
    state["scenario"] = a.scenario

    def on_message(c, u, msg):
        try:
            sc = json.loads(msg.payload).get("scenario")
        except ValueError:
            return
        if sc in PROFILES:
            state["scenario"] = sc
            print("Escenario ->", sc)

    cli = make_client()
    cli.on_message = on_message
    cli.on_connect = lambda c, *args: c.subscribe("sat/forest/control", qos=1)
    cli.connect(a.host, a.port)
    cli.loop_start()
    if not a.no_input:
        def kb():
            while True:
                try:
                    s = input("Escenario (normal/seco/incendio): ").strip()
                except EOFError:
                    return
                if s in PROFILES:
                    state["scenario"] = s
        threading.Thread(target=kb, daemon=True).start()
    print(f"Simulando {len(NODES)} nodos cada {a.interval}s (escenario {a.scenario})")
    while True:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for nid, (lat, lon) in NODES.items():
            msg = {"node_id": nid, "lat": lat, "lon": lon, "ts": ts, "simulated": True, **reading(nid)}
            cli.publish(f"sat/forest/{nid}/telemetry", json.dumps(msg), qos=1)
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
