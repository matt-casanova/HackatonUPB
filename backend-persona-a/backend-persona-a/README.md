# SAT Bolivia – Backend de incendios (Persona A)

> Carpeta `backend-persona-a/` del repo HackatonUPB. Solo la edita la Persona A; la app Android (Persona B) vive en `app/` y la raíz de Gradle. Rama sugerida: `feature/fire-backend`.

FastAPI + MQTT + NASA FIRMS + Open-Meteo + SQLite/Turso + Telegram. Contrato API v1 para Android.

## Arranque rápido (hora 0-1)
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # Windows: copy .env.example .env
# broker de demo: mosquitto -c mosquitto_demo.conf -v
# Hora 1: entregar mock a Persona B -> poner MOCK_MODE=true en .env
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# http://localhost:8000/health   y   /docs
```
Emulador Android -> `http://10.0.2.2:8000/`. Teléfono físico -> `http://<IP-LAN-de-tu-laptop>:8000/`.

## Cadena completa (hora 1-6)
```bash
mosquitto -v                                   # broker en :1883
MOCK_MODE=false uvicorn app.main:app --host 0.0.0.0 --port 8000
python simulator/mqtt_simulator.py             # 3 nodos CHI-01..03, cada 5 s
```
Si Mosquitto rechaza conexiones: en `mosquitto.conf` añade `listener 1883` y `allow_anonymous true`.

## Claves (solo en `.env`; NUNCA en Git ni en la APK)
| Servicio | Cómo obtenerla |
|---|---|
| `FIRMS_MAP_KEY` | https://firms.modaps.eosdis.nasa.gov/api/map_key/ (gratis, con correo). Sin clave: `firms.status=disabled` y se usa foco DEMO |
| `TURSO_URL`, `TURSO_TOKEN` | `turso db create sat-fire` -> `turso db show sat-fire --url` -> `turso db tokens create sat-fire`. Se usa la API HTTP (sin driver). Si falla, cae solo a SQLite local |
| `TELEGRAM_BOT_TOKEN` | @BotFather -> /newbot. Escribe `/id` al bot y copia tu chat_id a `TELEGRAM_CHAT_IDS` (varios, separados por coma) |
| `DEMO_TOKEN` | Opcional. Si se define, POST confirm/false-alarm/demo exigen header `X-Demo-Token` |

## Contrato (lo que consume Persona B)
| Ruta | Respuesta |
|---|---|
| `GET /health` | `{"status":"ok"}` |
| `GET /api/v1/fires/overview` | objeto canónico; campos numéricos siempre no-nulos |
| `GET /api/v1/fires/points` | `{"points":[...]}`; `IOT_NODE` con riesgo; `SATELLITE_HOTSPOT` sin `risk_*` (con `frp/confidence/acquired_at` opcionales) |
| `GET /api/v1/fires/history?node_id=CHI-01&limit=100` | `{"node_id","history":[{ts,risk_score,risk_level,source_mode}]}` ascendente; 404 si el nodo no existe |
| `GET /api/v1/alerts[?status=PENDING]` | `{"alerts":[{id,node_id,risk_score,status,created_at,decided_at,confirmed_by,source_mode}]}` |
| `POST /api/v1/alerts/{id}/confirm` y `/false-alarm` | body `{"operator":"..."}` -> alerta actualizada. **404** no existe, **409** ya resuelta (cualquier repetición), 401 token, 422 body |

`risk_level`: NORMAL (<40), WARNING (40-69), CRITICAL (>=70). `source_mode`: LIVE, DEMO, STALE. `status`: PENDING, CONFIRMED, FALSE_ALARM. Timestamps UTC ISO 8601 con `Z`.

Extras para demo/evidencia: `GET /api/v1/system/status`, `POST /api/v1/demo/scenario {"scenario":"normal|seco|incendio"}`, `POST /api/v1/demo/hotspot {"active":true,"node_id":"CHI-01"}`, `POST /api/v1/demo/reset`.

## Guion de demo con curl
```bash
curl -XPOST localhost:8000/api/v1/demo/reset
curl -XPOST localhost:8000/api/v1/demo/scenario -H 'content-type: application/json' -d '{"scenario":"seco"}'      # WARNING
curl -XPOST localhost:8000/api/v1/demo/scenario -H 'content-type: application/json' -d '{"scenario":"incendio"}'  # CRITICAL (75) -> alerta + Telegram
curl -XPOST localhost:8000/api/v1/demo/hotspot  -H 'content-type: application/json' -d '{"active":true}'          # 100 (foco DEMO a ~4.7 km)
```
(Con `DEMO_TOKEN` añade `-H 'X-Demo-Token: ...'`.) También puedes teclear el escenario en la consola del simulador.

## Cómo se calcula el score
temp 0/12/25 (>=33/>=40) + humedad 0/10/20 (<=35/<=20) + viento 0/8/15 (>=20/>=30) + humo 0/8/15 (>=.30/>=.65) + foco a <=10 km +25; tope 100.
Temperatura, humedad y humo vienen del nodo; el viento viene de Open-Meteo (máximo de las próximas 3 h) porque el nodo no tiene anemómetro. Un dato faltante no suma puntos. En los escenarios `seco`/`incendio` el viento se fija (22/32 km/h) y queda marcado DEMO.
Es una heurística no calibrada: no es IA entrenada ni una probabilidad.

## Consistencia y anti-duplicados
* Una sola alerta PENDING por nodo (índice único parcial en la BD + comprobación previa) y enfriamiento `ALERT_COOLDOWN_SECONDS` (120 s en demo; 900 en producción).
* Transición con `UPDATE ... WHERE status='PENDING'` verificando filas afectadas. API y Telegram usan la misma función (`Engine.transition_alert`).
* Se descartan lecturas con rangos imposibles, `ts` de más de 10 min atrás o 2 min en el futuro, no posteriores a la anterior, o con `node_id` distinto al del tópico.

## Contingencias
| Falla | Comportamiento |
|---|---|
| Turso no conecta | SQLite local automático (`/system/status -> db.backend`) |
| FIRMS vacío, timeout o clave mala | No cae; conserva el último dato; `firms.status` = empty/error; usa foco DEMO |
| Open-Meteo caído | Usa caché; si no hay, viento 0 y `weather.status=error` |
| Broker caído | La API sigue viva; reconecta sola; `mqtt_connected=false` |
| Sin telemetría > 60 s | `source_mode = STALE` |

## Pruebas
`pytest -q` (12 pruebas: score, validación, fusión, alerta única, cooldown, 404/409, token, mock, Telegram).
Verificado además con broker MQTT real + simulador + curl.

## Honestidad técnica
MQTT simulado no es LoRaWAN físico. El score es heurístico. FIRMS tiene retraso de horas y un CSV vacío no significa ausencia de riesgo. La confirmación es un ejercicio, no una alerta oficial.
