import os, sys
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.db import LocalDB, init_schema
from app.engine import Engine, validate_telemetry
from app.main import create_app
from app.risk import haversine_km, risk_score
from app.sources import FirmsStore, parse_firms_csv


class FakeWeather:
    def __init__(self, wind=32.0):
        self.wind = wind

    def get(self, lat, lon):
        return {"wind_kmh": self.wind}

    def info(self):
        return {"status": "fake"}


def make(wind=32.0, **kw):
    s = Settings(turso_url="", turso_token="", telegram_token="", demo_token="", mock_mode=False,
                 firms_map_key="", **kw)
    db = LocalDB(":memory:")
    init_schema(db)
    return s, Engine(s, db, FirmsStore(s), FakeWeather(wind))


def tel(node="CHI-01", t=42.0, h=18, smoke=0.85, ts=None, **kw):
    d = {"node_id": node, "lat": -16.39, "lon": -61.05, "temperature_c": t, "humidity_pct": h,
         "smoke_index": smoke, "simulated": True}
    if ts:
        d["ts"] = ts
    return {**d, **kw}


def test_score_thresholds():
    assert risk_score(42, 18, 32, .85, 0)[0] == 75
    assert risk_score(42, 18, 32, .85, 2) == (100, "CRITICAL")
    assert risk_score(29, 55, 10, .1, 0) == (0, "NORMAL")
    assert risk_score(41, 30, 0, .35, 0) == (43, "WARNING")
    assert risk_score(None, None, None, None, 0)[0] == 0


def test_haversine():
    assert abs(haversine_km(-16.39, -61.05, -16.42, -61.08) - 4.7) < 0.3


def test_validation_rejects_bad_data():
    now = datetime.now(timezone.utc)
    for bad in (tel(h=140), tel(smoke=2), tel(node="a b"), {"node_id": "X"},
                tel(ts=(now - timedelta(hours=2)).isoformat()),
                tel(ts=(now + timedelta(hours=1)).isoformat())):
        with pytest.raises(ValueError):
            validate_telemetry(bad, now)


def test_out_of_order_rejected():
    _, e = make()
    now = datetime.now(timezone.utc)
    e.process_telemetry(tel(), now=now)
    with pytest.raises(ValueError):
        e.process_telemetry(tel(ts=(now - timedelta(seconds=30)).isoformat()), now=now)


def test_single_pending_alert_and_cooldown():
    _, e = make(alert_cooldown_s=120)
    got = []
    e.on_alert.append(got.append)
    now = datetime.now(timezone.utc)
    for i in range(5):  # 5 lecturas criticas -> UNA alerta
        e.process_telemetry(tel(), now=now + timedelta(seconds=i))
    assert len(got) == 1 and got[0]["status"] == "PENDING" and got[0]["source_mode"] == "DEMO"
    e.transition_alert(got[0]["id"], "CONFIRMED", "test")
    e.process_telemetry(tel(), now=now + timedelta(seconds=10))  # cooldown activo
    assert len(got) == 1
    e.process_telemetry(tel(), now=now + timedelta(seconds=400))  # cooldown vencido
    assert len(got) == 2


def test_transitions_404_409():
    _, e = make()
    from app.engine import AlertAlreadyDecided, AlertNotFound
    e.process_telemetry(tel())
    a = e.list_alerts()[0]
    with pytest.raises(AlertNotFound):
        e.transition_alert(999, "CONFIRMED", "x")
    r = e.transition_alert(a["id"], "CONFIRMED", "op1")
    assert r["status"] == "CONFIRMED" and r["confirmed_by"] == "op1" and r["decided_at"]
    with pytest.raises(AlertAlreadyDecided):
        e.transition_alert(a["id"], "FALSE_ALARM", "op2")
    assert e.get_alert(a["id"])["status"] == "CONFIRMED"


def test_hotspot_fusion():
    _, e = make(wind=10.0)
    now = datetime.now(timezone.utc)
    e.process_telemetry(tel(t=29, h=55, smoke=.1), now=now)
    e.set_demo_hotspot("CHI-01", True)
    r = e.process_telemetry(tel(t=29, h=55, smoke=.1), now=now + timedelta(seconds=5))
    assert r["hotspots_near"] == 1 and r["score"] == 25 and r["source_mode"] == "DEMO"
    assert e.overview()["active_hotspots"] == 1
    assert any(p["type"] == "SATELLITE_HOTSPOT" for p in e.points())


def test_firms_parser():
    csv_ = ("latitude,longitude,bright_ti4,acq_date,acq_time,confidence,frp\n"
            "-16.4,-61.0,340,2026-11-06,1830,n,12.5\n-16.5,-61.1,300,2026-11-06,1830,l,1\n")
    s = parse_firms_csv(csv_)
    assert len(s) == 1 and s[0]["frp"] == 12.5
    assert parse_firms_csv("") == []
    with pytest.raises(ValueError):
        parse_firms_csv("Invalid MAP_KEY")


def test_api_end_to_end():
    s, e = make()
    app = create_app(s, engine=e, start_workers=False)
    c = TestClient(app)
    assert c.get("/health").json() == {"status": "ok"}
    o = c.get("/api/v1/fires/overview").json()
    assert o["source_mode"] == "STALE" and o["risk_score"] == 0
    e.process_telemetry(tel())
    o = c.get("/api/v1/fires/overview").json()
    assert o["risk_level"] == "CRITICAL" and o["source_mode"] == "DEMO"
    pts = c.get("/api/v1/fires/points").json()["points"]
    assert pts[0]["id"] == "CHI-01" and "frp" not in pts[0]
    assert len(c.get("/api/v1/fires/history", params={"node_id": "CHI-01"}).json()["history"]) == 1
    assert c.get("/api/v1/fires/history", params={"node_id": "NOPE"}).status_code == 404
    al = c.get("/api/v1/alerts").json()["alerts"]
    assert len(al) == 1 and al[0]["decided_at"] is None
    aid = al[0]["id"]
    assert c.post(f"/api/v1/alerts/{aid}/confirm", json={"operator": ""}).status_code == 422
    r = c.post(f"/api/v1/alerts/{aid}/confirm", json={"operator": "demo"})
    assert r.status_code == 200 and r.json()["status"] == "CONFIRMED"
    assert c.post(f"/api/v1/alerts/{aid}/confirm", json={"operator": "demo"}).status_code == 409
    assert c.post("/api/v1/alerts/999/false-alarm", json={"operator": "demo"}).status_code == 404
    assert c.post("/api/v1/demo/hotspot", json={"active": True, "node_id": "CHI-01"}).status_code == 200
    assert c.post("/api/v1/demo/scenario", json={"scenario": "seco"}).status_code == 200
    assert c.get("/api/v1/system/status").json()["db"]["backend"] == "sqlite"
    assert c.post("/api/v1/demo/reset").status_code == 200


def test_token_protection():
    s, e = make()
    s.demo_token = "secreto"
    c = TestClient(create_app(s, engine=e, start_workers=False))
    assert c.post("/api/v1/alerts/1/confirm", json={"operator": "x"}).status_code == 401
    assert c.post("/api/v1/alerts/1/confirm", json={"operator": "x"},
                  headers={"X-Demo-Token": "secreto"}).status_code == 404


def test_mock_mode():
    s, e = make()
    s.mock_mode = True
    c = TestClient(create_app(s, engine=e, start_workers=False))
    assert c.get("/api/v1/fires/overview").json()["risk_score"] == 85
    assert len(c.get("/api/v1/fires/points").json()["points"]) == 2
    assert c.post("/api/v1/alerts/1/confirm", json={"operator": "x"}).json()["status"] == "CONFIRMED"


def test_telegram_commands():
    from app.telegram_bot import TelegramBot
    s, e = make()
    s.telegram_token, s.telegram_chat_ids = "tok", ["42"]
    bot = TelegramBot(s, e)
    sent = []
    bot.send = lambda cid, txt: sent.append((cid, txt))
    e.on_decision.append(bot.notify_decision)
    e.process_telemetry(tel())
    aid = e.list_alerts()[0]["id"]
    upd = lambda cid, t: {"message": {"chat": {"id": cid}, "text": t}}
    bot.handle_update(upd(7, f"/confirm {aid}"))           # no autorizado
    assert e.get_alert(aid)["status"] == "PENDING"
    bot.handle_update(upd(42, f"/confirm {aid}"))
    assert e.get_alert(aid)["status"] == "CONFIRMED" and e.get_alert(aid)["confirmed_by"] == "telegram:42"
    bot.handle_update(upd(42, f"/false {aid}"))
    assert "ya estaba CONFIRMED" in sent[-1][1]
