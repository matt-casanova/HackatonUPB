import sqlite3
c = sqlite3.connect("sat_fire.db")
print("== Filas por tabla")
for t in ("telemetry", "risk_events", "alerts"):
    print(t, c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
print("== Ultimas alertas")
for r in c.execute("SELECT id,node_id,risk_score,status,confirmed_by,created_at,decided_at FROM alerts ORDER BY id DESC LIMIT 5"):
    print(r)
print("== Ultimos riesgos")
for r in c.execute("SELECT node_id,ts,risk_score,risk_level,source_mode FROM risk_events ORDER BY id DESC LIMIT 5"):
    print(r)
print("== PENDING por nodo (debe ser 0 o 1)")
for r in c.execute("SELECT node_id,COUNT(*) FROM alerts WHERE status='PENDING' GROUP BY node_id"):
    print(r)
print("== Indice anti-duplicados")
print(c.execute("SELECT name FROM sqlite_master WHERE name='ux_alert_pending'").fetchall())
