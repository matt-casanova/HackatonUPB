"""Nucleo: validacion -> fusion -> score -> persistencia -> alertas -> confirmacion."""
from __future__ import annotations
import logging, re, threading
from datetime import datetime, timezone
from .db import DBError
from .risk import risk_score

log = logging.getLogger("sat.engine")
NODE_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
WIND_OVERRIDE = {"normal": None, "seco": 22.0, "incendio": 32.0}  # solo modo DEMO


class AlertNotFound(Exception):
    pass


class AlertAlreadyDecided(Exception):
    def __init__(self, alert):
        super().__init__("alerta ya resuelta")
        self.alert = alert


def utcnow():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(s):
    d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def validate_telemetry(p, now, max_age_s=600, max_future_s=120):
    """Valida rangos y timestamps; lanza ValueError si la lectura es inconsistente."""
    if not isinstance(p, dict):
        raise ValueError("payload no es un objeto JSON")
    for k in ("node_id", "lat", "lon", "temperature_c", "humidity_pct", "smoke_index"):
        if k not in p:
            raise ValueError(f"falta el campo {k}")
    nid = str(p["node_id"])
    if not NODE_RE.match(nid):
        raise ValueError("node_id invalido")
    try:
        lat, lon, t, h, sm = (float(p[k]) for k in
                              ("lat", "lon", "temperature_c", "humidity_pct", "smoke_index"))
    except (TypeError, ValueError):
        raise ValueError("valores no numericos")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("coordenadas fuera de rango")
    if not (-30 <= t <= 70):
        raise ValueError("temperatura fuera de rango")
    if not (0 <= h <= 100):
        raise ValueError("humedad fuera de rango")
    if not (0 <= sm <= 1):
        raise ValueError("smoke_index fuera de 0..1")
    ts = now
    if "ts" in p:
        try:
            ts = parse_ts(p["ts"])
        except (TypeError, ValueError):
            raise ValueError("ts invalido")
        delta = (now - ts).total_seconds()
        if delta > max_age_s:
            raise ValueError("timestamp demasiado antiguo")
        if delta < -max_future_s:
            raise ValueError("timestamp en el futuro")
    return {"node_id": nid, "ts": ts, "lat": lat, "lon": lon, "temperature_c": t,
            "humidity_pct": h, "smoke_index": sm, "simulated": bool(p.get("simulated", False))}


class Engine:
    def __init__(self, settings, db, hotspots, weather):
        self.s, self.db, self.hotspots, self.weather = settings, db, hotspots, weather
        self.lock = threading.RLock()
        self.latest = {}  # node_id -> {"telemetry":{...}, "risk":{...}}
        self.demo = {"scenario": "normal", "wind_override": None}
        self.on_alert, self.on_decision = [], []
        self.control_publisher = None
        self.cooldown_ignore_before = None
        self.stats = {"received": 0, "accepted": 0, "rejected": 0, "db_errors": 0, "last_error": None}
        self.load_state()

    # ---------- arranque ----------
    def load_state(self):
        try:
            tel = self.db.execute(
                "SELECT t.* FROM telemetry t JOIN (SELECT node_id, MAX(id) mid FROM telemetry "
                "GROUP BY node_id) m ON t.id=m.mid").rows
            risk = {r["node_id"]: r for r in self.db.execute(
                "SELECT r.* FROM risk_events r JOIN (SELECT node_id, MAX(id) mid FROM risk_events "
                "GROUP BY node_id) m ON r.id=m.mid").rows}
        except DBError as e:
            log.warning("No se pudo cargar estado previo: %s", e)
            return
        for t in tel:
            r = risk.get(t["node_id"])
            self.latest[t["node_id"]] = {
                "telemetry": {"ts": parse_ts(t["ts"]), "lat": t["lat"], "lon": t["lon"],
                              "temperature_c": t["temperature_c"], "humidity_pct": t["humidity_pct"],
                              "smoke_index": t["smoke_index"], "simulated": bool(t["simulated"])},
                "risk": {"score": r["risk_score"], "level": r["risk_level"],
                         "source_mode": r["source_mode"], "wind_kmh": r["wind_kmh"] or 0.0,
                         "hotspots_near": r["hotspots_near"] or 0, "nearest_km": None} if r else None}

    # ---------- ingesta ----------
    def process_telemetry(self, payload, now=None):
        now = now or utcnow()
        self.stats["received"] += 1
        try:
            tel = validate_telemetry(payload, now)
            prev = self.latest.get(tel["node_id"])
            if prev and tel["ts"] <= prev["telemetry"]["ts"]:
                raise ValueError("timestamp no posterior a la ultima lectura")
        except ValueError as e:
            self.stats["rejected"] += 1
            self.stats["last_error"] = str(e)
            raise
        weather = self.weather.get(tel["lat"], tel["lon"])  # red fuera del lock (con cache)
        new_alert = None
        with self.lock:
            wind, wind_demo = self.demo["wind_override"], False
            if wind is not None:
                wind_demo = True
            elif weather:
                wind = weather["wind_kmh"]
            else:
                wind = 0.0
            near = self.hotspots.near(tel["lat"], tel["lon"], self.s.hotspot_radius_km)
            score, level = risk_score(tel["temperature_c"], tel["humidity_pct"], wind,
                                      tel["smoke_index"], len(near))
            demo_hot = any(p.get("demo") for p in near)
            mode = "DEMO" if (tel["simulated"] or wind_demo or demo_hot) else "LIVE"
            risk = {"score": score, "level": level, "source_mode": mode, "wind_kmh": float(wind),
                    "hotspots_near": len(near),
                    "nearest_km": min((p["distance_km"] for p in near), default=None)}
            self.latest[tel["node_id"]] = {"telemetry": tel, "risk": risk}
            self.stats["accepted"] += 1
            try:
                ts = iso(tel["ts"])
                self.db.execute(
                    "INSERT INTO telemetry (node_id, ts, lat, lon, temperature_c, humidity_pct, "
                    "smoke_index, simulated) VALUES (?,?,?,?,?,?,?,?)",
                    (tel["node_id"], ts, tel["lat"], tel["lon"], tel["temperature_c"],
                     tel["humidity_pct"], tel["smoke_index"], int(tel["simulated"])))
                rid = self.db.execute(
                    "INSERT INTO risk_events (node_id, ts, risk_score, risk_level, source_mode, "
                    "wind_kmh, hotspots_near) VALUES (?,?,?,?,?,?,?)",
                    (tel["node_id"], ts, score, level, mode, float(wind), len(near))).last_id
                if level == "CRITICAL":
                    new_alert = self._maybe_alert(tel["node_id"], rid, score, mode, now)
            except DBError as e:  # el sistema sigue vivo; el estado en memoria se mantiene
                self.stats["db_errors"] += 1
                self.stats["last_error"] = f"DB: {e}"
                log.error("Error de base de datos: %s", e)
        if new_alert:
            self._fire(self.on_alert, new_alert)
        return risk

    def _maybe_alert(self, node_id, risk_event_id, score, mode, now):
        if self.db.execute("SELECT id FROM alerts WHERE node_id=? AND status='PENDING' LIMIT 1",
                           (node_id,)).rows:
            return None  # ya hay una pendiente
        last = self.db.execute("SELECT created_at, decided_at FROM alerts WHERE node_id=? "
                               "ORDER BY id DESC LIMIT 1", (node_id,)).rows
        if last:
            ref = parse_ts(last[0]["decided_at"] or last[0]["created_at"])
            ignored = self.cooldown_ignore_before and ref < self.cooldown_ignore_before
            if not ignored and (now - ref).total_seconds() < self.s.alert_cooldown_s:
                return None  # enfriamiento
        try:
            res = self.db.execute(
                "INSERT INTO alerts (risk_event_id, node_id, status, created_at, risk_score, "
                "source_mode) VALUES (?,?,?,?,?,?)",
                (risk_event_id, node_id, "PENDING", iso(now), score, mode))
        except DBError as e:
            if e.unique:
                return None
            raise
        return self.get_alert(res.last_id)

    # ---------- alertas ----------
    @staticmethod
    def _alert_row(r):
        return {k: r[k] for k in ("id", "node_id", "risk_score", "status", "created_at",
                                  "decided_at", "confirmed_by", "source_mode")}

    def get_alert(self, alert_id):
        rows = self.db.execute("SELECT * FROM alerts WHERE id=?", (alert_id,)).rows
        return self._alert_row(rows[0]) if rows else None

    def list_alerts(self, status=None, limit=100):
        if status:
            rows = self.db.execute("SELECT * FROM alerts WHERE status=? ORDER BY id DESC LIMIT ?",
                                   (status, limit)).rows
        else:
            rows = self.db.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,)).rows
        return [self._alert_row(r) for r in rows]

    def transition_alert(self, alert_id, status, actor):
        """Funcion UNICA de transicion (la usan FastAPI y Telegram)."""
        if status not in ("CONFIRMED", "FALSE_ALARM"):
            raise ValueError("estado invalido")
        with self.lock:
            res = self.db.execute(
                "UPDATE alerts SET status=?, decided_at=?, confirmed_by=? "
                "WHERE id=? AND status='PENDING'", (status, iso(utcnow()), actor, alert_id))
            alert = self.get_alert(alert_id)
            if res.rowcount != 1:
                if alert is None:
                    raise AlertNotFound(alert_id)
                raise AlertAlreadyDecided(alert)
        self._fire(self.on_decision, alert)
        return alert

    def _fire(self, callbacks, alert):
        for cb in callbacks:
            try:
                cb(alert)
            except Exception:
                log.exception("callback de notificacion fallo")

    # ---------- consultas para la API ----------
    def _age(self, node):
        return (utcnow() - node["telemetry"]["ts"]).total_seconds()

    def overview(self):
        nodes = [n for n in self.latest.values() if n["risk"]]
        base = {"region": self.s.region, "risk_score": 0, "risk_level": "NORMAL",
                "temperature_c": 0.0, "humidity_pct": 0.0, "wind_kmh": 0.0, "smoke_index": 0.0,
                "active_hotspots": len(self.hotspots.all_points()), "source_mode": "STALE",
                "updated_at": iso(utcnow())}
        if not nodes:
            return base
        top = max(nodes, key=lambda n: n["risk"]["score"])
        fresh = [n for n in nodes if self._age(n) <= self.s.stale_after_s]
        if not fresh:
            mode = "STALE"
        elif any(n["risk"]["source_mode"] == "DEMO" for n in fresh):
            mode = "DEMO"
        else:
            mode = "LIVE"
        t = top["telemetry"]
        base.update(risk_score=top["risk"]["score"], risk_level=top["risk"]["level"],
                    temperature_c=t["temperature_c"], humidity_pct=t["humidity_pct"],
                    wind_kmh=top["risk"]["wind_kmh"], smoke_index=t["smoke_index"], source_mode=mode,
                    updated_at=iso(max(n["telemetry"]["ts"] for n in nodes)))
        return base

    def points(self):
        pts = []
        for nid, n in sorted(self.latest.items()):
            if not n["risk"]:
                continue
            mode = "STALE" if self._age(n) > self.s.stale_after_s else n["risk"]["source_mode"]
            pts.append({"id": nid, "type": "IOT_NODE", "lat": n["telemetry"]["lat"],
                        "lon": n["telemetry"]["lon"], "risk_score": n["risk"]["score"],
                        "risk_level": n["risk"]["level"], "source_mode": mode})
        for p in self.hotspots.all_points():
            pts.append({"id": p["id"], "type": "SATELLITE_HOTSPOT", "lat": p["lat"], "lon": p["lon"],
                        "source_mode": "DEMO" if p.get("demo") else "LIVE", "frp": p.get("frp"),
                        "confidence": p.get("confidence"), "acquired_at": p.get("acquired_at")})
        return pts

    def history(self, node_id, limit=100):
        rows = self.db.execute("SELECT ts, risk_score, risk_level, source_mode FROM risk_events "
                               "WHERE node_id=? ORDER BY id DESC LIMIT ?", (node_id, limit)).rows
        return list(reversed(rows))

    # ---------- modo DEMO ----------
    def set_scenario(self, name):
        if name not in WIND_OVERRIDE:
            raise ValueError("escenario invalido")
        self.demo["scenario"] = name
        self.demo["wind_override"] = WIND_OVERRIDE[name]
        if self.control_publisher:
            self.control_publisher({"scenario": name})

    def set_demo_hotspot(self, node_id, active):
        n = self.latest.get(node_id)
        if not n:
            raise ValueError(f"nodo desconocido: {node_id}")
        self.hotspots.set_demo(node_id, n["telemetry"]["lat"], n["telemetry"]["lon"], active)

    def reset_demo(self):
        self.set_scenario("normal")
        self.hotspots.clear_demo()
        with self.lock:
            for a in self.list_alerts(status="PENDING"):
                self.db.execute("UPDATE alerts SET status='FALSE_ALARM', decided_at=?, "
                                "confirmed_by='system:demo-reset' WHERE id=? AND status='PENDING'",
                                (iso(utcnow()), a["id"]))
            self.cooldown_ignore_before = utcnow()
