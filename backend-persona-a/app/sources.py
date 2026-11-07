"""Fuentes externas: NASA FIRMS (focos) y Open-Meteo (clima)."""
from __future__ import annotations
import csv, io, logging, threading, time
from datetime import datetime, timezone
import requests
from .risk import haversine_km

log = logging.getLogger("sat.sources")


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_firms_csv(text: str):
    """Lista de focos. CSV vacio -> []. Respuesta de error (texto) -> ValueError."""
    if not text.strip():
        return []
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "latitude" not in reader.fieldnames:
        raise ValueError(f"respuesta FIRMS no es CSV: {text.strip()[:120]}")
    spots = []
    for r in reader:
        conf = (r.get("confidence") or "").strip().lower()
        if conf in ("l", "low"):
            continue  # descarta baja confianza VIIRS
        try:
            lat, lon = float(r["latitude"]), float(r["longitude"])
        except (KeyError, ValueError):
            continue
        hhmm = (r.get("acq_time") or "0000").zfill(4)
        spots.append({
            "id": f"HOT-{r.get('acq_date','')}-{hhmm}-{lat:.3f}_{lon:.3f}",
            "lat": lat, "lon": lon, "demo": False,
            "frp": float(r["frp"]) if r.get("frp") not in (None, "") else None,
            "confidence": conf or None,
            "acquired_at": f"{r.get('acq_date','')}T{hhmm[:2]}:{hhmm[2:]}:00Z"})
    return spots


class FirmsStore:
    def __init__(self, settings):
        self.s = settings
        self.lock = threading.Lock()
        self.real, self.demo = [], {}
        self.status = "pending" if settings.firms_map_key else "disabled"
        self.error, self.fetched_at = None, None

    def fetch_once(self):
        if not self.s.firms_map_key:
            self.status = "disabled"
            return
        url = (f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{self.s.firms_map_key}/"
               f"{self.s.firms_source}/{self.s.firms_bbox}/{self.s.firms_days}")
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            spots = parse_firms_csv(r.text)
        except Exception as e:  # timeout, HTTP, clave invalida...
            self.status, self.error = "error", str(e)[:200]
            log.warning("FIRMS error: %s", e)
            return  # conserva ultimos focos conocidos
        with self.lock:
            self.real = spots
        self.status = "ok" if spots else "empty"  # empty != sin riesgo
        self.error, self.fetched_at = None, _now_iso()

    def run_forever(self, stop):
        while not stop.is_set():
            self.fetch_once()
            stop.wait(self.s.firms_refresh_s)

    def all_points(self):
        with self.lock:
            return list(self.real) + list(self.demo.values())

    def near(self, lat, lon, radius_km):
        out = []
        for p in self.all_points():
            d = haversine_km(lat, lon, p["lat"], p["lon"])
            if d <= radius_km:
                out.append({**p, "distance_km": round(d, 2)})
        return out

    def set_demo(self, node_id, lat, lon, active):
        with self.lock:
            if active:  # ~4.7 km al suroeste del nodo
                self.demo[node_id] = {"id": f"HOT-DEMO-{node_id}", "lat": round(lat - 0.03, 5),
                                      "lon": round(lon - 0.03, 5), "demo": True, "frp": None,
                                      "confidence": "demo", "acquired_at": _now_iso()}
            else:
                self.demo.pop(node_id, None)

    def clear_demo(self):
        with self.lock:
            self.demo.clear()

    def info(self):
        return {"status": self.status, "error": self.error, "fetched_at": self.fetched_at,
                "real_hotspots": len(self.real), "demo_hotspots": len(self.demo)}


class WeatherClient:
    URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, settings):
        self.s = settings
        self.cache = {}
        self.status, self.error = "pending", None

    def get(self, lat, lon):
        key = (round(lat, 2), round(lon, 2))
        c = self.cache.get(key)
        if c and time.time() - c["_t"] < self.s.weather_ttl_s:
            return c
        try:
            r = requests.get(self.URL, params={
                "latitude": lat, "longitude": lon, "timezone": "UTC", "forecast_hours": 3,
                "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m",
                "wind_speed_unit": "kmh"}, timeout=8)
            r.raise_for_status()
            h = r.json()["hourly"]
            data = {"temperature_c": h["temperature_2m"][0],
                    "humidity_pct": h["relative_humidity_2m"][0],
                    "wind_kmh": max(h["wind_speed_10m"]),  # peor caso de las proximas 3 h
                    "origin": h["time"][0] + ":00Z", "fetched_at": _now_iso(), "_t": time.time()}
            self.cache[key] = data
            self.status, self.error = "ok", None
            return data
        except Exception as e:
            self.status, self.error = "error", str(e)[:200]
            log.warning("Open-Meteo error: %s", e)
            return {**c, "stale": True} if c else None

    def info(self):
        return {"status": self.status, "error": self.error, "cached_points": len(self.cache)}
