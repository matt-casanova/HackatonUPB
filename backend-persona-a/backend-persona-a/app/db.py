"""Capa de base de datos: Turso por HTTP (sin drivers) o SQLite local (plan B)."""
from __future__ import annotations
import logging, sqlite3, threading
import requests

log = logging.getLogger("sat.db")


class DBError(Exception):
    def __init__(self, msg, unique=False):
        super().__init__(msg)
        self.unique = unique


class Result:
    def __init__(self, rows, rowcount, last_id):
        self.rows, self.rowcount, self.last_id = rows, rowcount, last_id


SCHEMA = [
    """CREATE TABLE IF NOT EXISTS telemetry (
        id INTEGER PRIMARY KEY, node_id TEXT NOT NULL, ts TEXT NOT NULL,
        lat REAL, lon REAL, temperature_c REAL, humidity_pct REAL,
        smoke_index REAL, simulated INTEGER NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS risk_events (
        id INTEGER PRIMARY KEY, node_id TEXT NOT NULL, ts TEXT NOT NULL,
        risk_score INTEGER NOT NULL, risk_level TEXT NOT NULL, source_mode TEXT NOT NULL,
        wind_kmh REAL, hotspots_near INTEGER)""",
    """CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY, risk_event_id INTEGER NOT NULL, node_id TEXT NOT NULL,
        status TEXT NOT NULL, created_at TEXT NOT NULL, decided_at TEXT, confirmed_by TEXT,
        risk_score INTEGER, source_mode TEXT)""",
    "CREATE INDEX IF NOT EXISTS ix_tel_node ON telemetry(node_id, id)",
    "CREATE INDEX IF NOT EXISTS ix_risk_node ON risk_events(node_id, id)",
    # garantiza UNA alerta PENDING por nodo incluso con carreras
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_alert_pending ON alerts(node_id) WHERE status='PENDING'",
]


class LocalDB:
    backend = "sqlite"
    fallback_reason = None

    def __init__(self, path):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()

    def execute(self, sql, params=()):
        with self.lock:
            try:
                cur = self.conn.execute(sql, tuple(params))
                rows = [dict(r) for r in cur.fetchall()] if cur.description else []
                self.conn.commit()
                return Result(rows, cur.rowcount, cur.lastrowid)
            except sqlite3.Error as e:
                self.conn.rollback()
                raise DBError(str(e), unique="UNIQUE" in str(e).upper())


class TursoDB:
    """Turso/libSQL via API HTTP /v2/pipeline (solo requests, sin driver nativo)."""
    backend = "turso"
    fallback_reason = None

    def __init__(self, url, token, timeout=10):
        self.base = url.replace("libsql://", "https://").rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {token}"

    @staticmethod
    def _arg(v):
        if v is None:
            return {"type": "null"}
        if isinstance(v, bool):
            return {"type": "integer", "value": str(int(v))}
        if isinstance(v, int):
            return {"type": "integer", "value": str(v)}
        if isinstance(v, float):
            return {"type": "float", "value": v}
        return {"type": "text", "value": str(v)}

    @staticmethod
    def _val(c):
        t, v = c.get("type"), c.get("value")
        if t == "null" or v is None:
            return None
        return int(v) if t == "integer" else float(v) if t == "float" else v

    def execute(self, sql, params=()):
        body = {"requests": [
            {"type": "execute", "stmt": {"sql": sql, "args": [self._arg(p) for p in params]}},
            {"type": "close"}]}
        try:
            r = self.session.post(f"{self.base}/v2/pipeline", json=body, timeout=self.timeout)
        except requests.RequestException as e:
            raise DBError(f"Turso no alcanzable: {e}")
        if r.status_code != 200:
            raise DBError(f"Turso HTTP {r.status_code}: {r.text[:200]}")
        res = r.json()["results"][0]
        if res["type"] == "error":
            msg = res["error"].get("message", "error")
            raise DBError(msg, unique="UNIQUE" in msg.upper())
        out = res["response"]["result"]
        cols = [c["name"] for c in out["cols"]]
        rows = [{c: self._val(x) for c, x in zip(cols, row)} for row in out["rows"]]
        lid = out.get("last_insert_rowid")
        return Result(rows, out.get("affected_row_count", 0), int(lid) if lid is not None else None)


def init_schema(db):
    for stmt in SCHEMA:
        db.execute(stmt)


def make_db(settings):
    """Turso si hay credenciales y responde; si no, SQLite local (plan B del hito hora 4)."""
    reason = None
    if settings.turso_url and settings.turso_token:
        try:
            db = TursoDB(settings.turso_url, settings.turso_token)
            db.execute("SELECT 1")
            init_schema(db)
            log.info("Base de datos: Turso")
            return db
        except DBError as e:
            reason = str(e)
            log.warning("Turso fallo (%s). Usando SQLite local.", e)
    db = LocalDB(settings.db_path)
    db.fallback_reason = reason
    init_schema(db)
    return db
