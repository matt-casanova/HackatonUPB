"""Consulta REAL y por separado de Open-Meteo y NASA FIRMS (evidencia T10)."""
import csv, io, os, sys
import requests
from dotenv import load_dotenv

load_dotenv()
NODES = {"CHI-01": (-16.39, -61.05), "CHI-02": (-16.75, -60.70), "CHI-03": (-17.20, -61.40)}

print("=== Open-Meteo (origen: api.open-meteo.com, dato real) ===")
for nid, (lat, lon) in NODES.items():
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast", timeout=20, params={
            "latitude": lat, "longitude": lon, "timezone": "UTC",
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m"})
        r.raise_for_status()
        c = r.json()["current"]
        print(f"{nid}: {c['temperature_2m']} C | {c['relative_humidity_2m']} % | "
              f"{c['wind_speed_10m']} km/h | hora {c['time']} UTC")
    except Exception as e:
        print(f"{nid}: ERROR ({type(e).__name__})")

print("\n=== NASA FIRMS VIIRS (origen: firms.modaps.eosdis.nasa.gov, dato real) ===")
key = os.getenv("FIRMS_MAP_KEY", "").strip()
bbox = os.getenv("FIRMS_BBOX", "-63.0,-20.0,-58.0,-15.0")
if not key:
    print("Sin FIRMS_MAP_KEY en .env: no se consulta (el sistema usa foco DEMO etiquetado).")
    sys.exit(0)
try:
    r = requests.get(f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_SNPP_NRT/{bbox}/1", timeout=30)
    r.raise_for_status()
    if not r.text.startswith("latitude"):
        print("Respuesta inesperada (clave invalida o limite de consultas):", r.text[:120].replace(key, "***"))
        sys.exit(0)
    rows = list(csv.DictReader(io.StringIO(r.text)))
    print(f"Focos VIIRS en las ultimas 24 h dentro de la caja {bbox}: {len(rows)}")
    for f in rows[:5]:
        print(f"  lat {f['latitude']} lon {f['longitude']} | {f['acq_date']} {f['acq_time']} UTC | conf {f['confidence']} | FRP {f['frp']}")
    if not rows:
        print("Vacio: no hay focos ahora. Esto NO significa ausencia de riesgo.")
except Exception as e:
    print(f"ERROR FIRMS ({type(e).__name__}). El sistema sigue operando y marca la fuente como faltante.")
