"""API FastAPI del modulo de incendios (Persona A). Contrato congelado v1."""
from __future__ import annotations
import hmac, logging, threading
from contextlib import asynccontextmanager
from typing import Literal, Optional
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field
from .config import Settings
from .db import make_db
from .engine import AlertAlreadyDecided, AlertNotFound, Engine
from .mqtt_consumer import MqttConsumer
from .sources import FirmsStore, WeatherClient
from .telegram_bot import TelegramBot

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


class Overview(BaseModel):
    region: str
    risk_score: int
    risk_level: str
    temperature_c: float
    humidity_pct: float
    wind_kmh: float
    smoke_index: float
    active_hotspots: int
    source_mode: str
    updated_at: str


class Point(BaseModel):
    id: str
    type: str
    lat: float
    lon: float
    risk_score: Optional[int] = None
    risk_level: Optional[str] = None
    source_mode: str
    frp: Optional[float] = None
    confidence: Optional[str] = None
    acquired_at: Optional[str] = None


class PointsOut(BaseModel):
    points: list[Point]


class AlertOut(BaseModel):
    id: int
    node_id: str
    risk_score: int
    status: str
    created_at: str
    decided_at: Optional[str] = None
    confirmed_by: Optional[str] = None
    source_mode: str


class AlertsOut(BaseModel):
    alerts: list[AlertOut]


class HistoryItem(BaseModel):
    ts: str
    risk_score: int
    risk_level: str
    source_mode: str


class HistoryOut(BaseModel):
    node_id: str
    history: list[HistoryItem]


class ConfirmBody(BaseModel):
    operator: str = Field(min_length=1, max_length=64)


class ScenarioBody(BaseModel):
    scenario: Literal["normal", "seco", "incendio"]


class HotspotBody(BaseModel):
    active: bool
    node_id: str = "CHI-01"


MOCK_OVERVIEW = {"region": "Chiquitania", "risk_score": 85, "risk_level": "CRITICAL",
                 "temperature_c": 42.0, "humidity_pct": 18.0, "wind_kmh": 32.0, "smoke_index": 0.85,
                 "active_hotspots": 2, "source_mode": "DEMO", "updated_at": "2026-11-06T18:00:00Z"}
MOCK_POINTS = [
    {"id": "CHI-01", "type": "IOT_NODE", "lat": -16.39, "lon": -61.05, "risk_score": 85,
     "risk_level": "CRITICAL", "source_mode": "DEMO"},
    {"id": "HOT-DEMO-01", "type": "SATELLITE_HOTSPOT", "lat": -16.42, "lon": -61.08, "source_mode": "DEMO"}]
MOCK_ALERT = {"id": 1, "node_id": "CHI-01", "risk_score": 85, "status": "PENDING",
              "created_at": "2026-11-06T18:00:00Z", "decided_at": None, "confirmed_by": None,
              "source_mode": "DEMO"}


def create_app(settings=None, engine=None, start_workers=True):
    settings = settings or Settings()
    stop = threading.Event()
    if engine is None:
        engine = Engine(settings, make_db(settings), FirmsStore(settings), WeatherClient(settings))
    bot = TelegramBot(settings, engine)
    engine.on_alert.append(bot.notify_alert)
    engine.on_decision.append(bot.notify_decision)
    consumer = MqttConsumer(settings, engine)
    engine.control_publisher = consumer.publish_control

    @asynccontextmanager
    async def lifespan(app):
        if start_workers:
            consumer.start()
            threading.Thread(target=engine.hotspots.run_forever, args=(stop,), daemon=True).start()
            threading.Thread(target=bot.run_forever, args=(stop,), daemon=True).start()
        yield
        stop.set()
        if start_workers:
            consumer.stop()

    app = FastAPI(title="SAT Bolivia - Incendios (MVP)", version="1.0", lifespan=lifespan)
    app.state.engine, app.state.bot, app.state.consumer = engine, bot, consumer

    def auth(x_demo_token: Optional[str] = Header(default=None)):
        if settings.demo_token and not hmac.compare_digest(x_demo_token or "", settings.demo_token):
            raise HTTPException(401, "X-Demo-Token invalido")

    def demo_only():
        if not settings.demo_mode:
            raise HTTPException(404, "modo demo deshabilitado")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/v1/fires/overview", response_model=Overview)
    def overview():
        return MOCK_OVERVIEW if settings.mock_mode else engine.overview()

    @app.get("/api/v1/fires/points", response_model=PointsOut, response_model_exclude_none=True)
    def points():
        return {"points": MOCK_POINTS if settings.mock_mode else engine.points()}

    @app.get("/api/v1/fires/history", response_model=HistoryOut)
    def history(node_id: str, limit: int = Query(100, ge=1, le=1000)):
        if settings.mock_mode:
            return {"node_id": node_id, "history": [
                {"ts": f"2026-11-06T17:{m:02d}:00Z", "risk_score": s, "risk_level": lv,
                 "source_mode": "DEMO"} for m, s, lv in
                ((50, 20, "NORMAL"), (52, 45, "WARNING"), (54, 70, "CRITICAL"), (56, 85, "CRITICAL"))]}
        if node_id not in engine.latest:
            raise HTTPException(404, f"nodo desconocido: {node_id}")
        return {"node_id": node_id, "history": engine.history(node_id, limit)}

    @app.get("/api/v1/alerts", response_model=AlertsOut)
    def alerts(status: Optional[Literal["PENDING", "CONFIRMED", "FALSE_ALARM"]] = None):
        if settings.mock_mode:
            return {"alerts": [MOCK_ALERT]}
        return {"alerts": engine.list_alerts(status)}

    def _decide(alert_id, status, operator):
        if settings.mock_mode:
            if alert_id != 1:
                raise HTTPException(404, "alerta no existe")
            return {**MOCK_ALERT, "status": status, "confirmed_by": operator,
                    "decided_at": "2026-11-06T18:05:00Z"}
        try:
            return engine.transition_alert(alert_id, status, operator)
        except AlertNotFound:
            raise HTTPException(404, "alerta no existe")
        except AlertAlreadyDecided as e:
            raise HTTPException(409, f"alerta ya resuelta ({e.alert['status']})")

    @app.post("/api/v1/alerts/{alert_id}/confirm", response_model=AlertOut, dependencies=[Depends(auth)])
    def confirm(alert_id: int, body: ConfirmBody):
        return _decide(alert_id, "CONFIRMED", body.operator)

    @app.post("/api/v1/alerts/{alert_id}/false-alarm", response_model=AlertOut, dependencies=[Depends(auth)])
    def false_alarm(alert_id: int, body: ConfirmBody):
        return _decide(alert_id, "FALSE_ALARM", body.operator)

    # ---------- extras para demo y evidencia ----------
    @app.get("/api/v1/system/status")
    def system_status():
        return {"mqtt_connected": consumer.connected, "queue": consumer.q.qsize(),
                "db": {"backend": engine.db.backend, "fallback_reason": engine.db.fallback_reason},
                "firms": engine.hotspots.info(), "weather": engine.weather.info(),
                "telegram": {"enabled": bot.enabled, "authorized_chats": len(bot.allowed),
                             "last_error": bot.last_error},
                "demo": engine.demo, "stats": engine.stats, "mock_mode": settings.mock_mode}

    @app.post("/api/v1/demo/scenario", dependencies=[Depends(auth), Depends(demo_only)])
    def demo_scenario(body: ScenarioBody):
        engine.set_scenario(body.scenario)
        return {"scenario": body.scenario}

    @app.post("/api/v1/demo/hotspot", dependencies=[Depends(auth), Depends(demo_only)])
    def demo_hotspot(body: HotspotBody):
        try:
            engine.set_demo_hotspot(body.node_id, body.active)
        except ValueError as e:
            raise HTTPException(404, str(e))
        return {"node_id": body.node_id, "active": body.active}

    @app.post("/api/v1/demo/reset", dependencies=[Depends(auth), Depends(demo_only)])
    def demo_reset():
        engine.reset_demo()
        return {"status": "reset"}

    return app


app = create_app()
