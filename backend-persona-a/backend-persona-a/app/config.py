from __future__ import annotations
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


def _s(name, default=""):
    return lambda: os.getenv(name, default).strip()


def _i(name, default):
    return lambda: int(os.getenv(name, str(default)))


def _f(name, default):
    return lambda: float(os.getenv(name, str(default)))


def _b(name, default):
    return lambda: os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    region: str = field(default_factory=_s("REGION", "Chiquitania"))
    mqtt_host: str = field(default_factory=_s("MQTT_HOST", "localhost"))
    mqtt_port: int = field(default_factory=_i("MQTT_PORT", 1883))
    mqtt_topic: str = "sat/forest/+/telemetry"
    mqtt_control_topic: str = "sat/forest/control"
    firms_map_key: str = field(default_factory=_s("FIRMS_MAP_KEY"))
    firms_source: str = field(default_factory=_s("FIRMS_SOURCE", "VIIRS_SNPP_NRT"))
    firms_bbox: str = field(default_factory=_s("FIRMS_BBOX", "-63.0,-20.0,-58.0,-15.0"))
    firms_days: int = field(default_factory=_i("FIRMS_DAYS", 1))
    firms_refresh_s: int = field(default_factory=_i("FIRMS_REFRESH_SECONDS", 600))
    hotspot_radius_km: float = field(default_factory=_f("HOTSPOT_RADIUS_KM", 10))
    weather_ttl_s: int = field(default_factory=_i("WEATHER_TTL_SECONDS", 600))
    db_path: str = field(default_factory=_s("DB_PATH", "sat_fire.db"))
    turso_url: str = field(default_factory=_s("TURSO_URL"))
    turso_token: str = field(default_factory=_s("TURSO_TOKEN"))
    telegram_token: str = field(default_factory=_s("TELEGRAM_BOT_TOKEN"))
    telegram_chat_ids: list = field(default_factory=lambda: [
        x.strip() for x in os.getenv("TELEGRAM_CHAT_IDS", "").split(",") if x.strip()])
    demo_token: str = field(default_factory=_s("DEMO_TOKEN"))
    demo_mode: bool = field(default_factory=_b("DEMO_MODE", True))
    mock_mode: bool = field(default_factory=_b("MOCK_MODE", False))
    alert_cooldown_s: int = field(default_factory=_i("ALERT_COOLDOWN_SECONDS", 120))
    stale_after_s: int = field(default_factory=_i("STALE_AFTER_SECONDS", 60))
