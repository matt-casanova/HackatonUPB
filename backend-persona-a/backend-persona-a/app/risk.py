"""Motor heuristico de riesgo (NO es IA entrenada ni probabilidad calibrada)."""
from __future__ import annotations
import math


def haversine_km(la1, lo1, la2, lo2) -> float:
    p1, p2 = math.radians(la1), math.radians(la2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2)
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def risk_level(score: int) -> str:
    return "CRITICAL" if score >= 70 else "WARNING" if score >= 40 else "NORMAL"


def risk_score(t, h, w, smoke, hotspots):
    """t=°C, h=% HR, w=km/h, smoke=0..1, hotspots=n focos dentro del radio."""
    # un dato faltante (None) NO suma puntos: nunca se interpreta como "muy seco"
    s = 0
    if t is not None:
        s += 25 if t >= 40 else 12 if t >= 33 else 0
    if h is not None:
        s += 20 if h <= 20 else 10 if h <= 35 else 0
    if w is not None:
        s += 15 if w >= 30 else 8 if w >= 20 else 0
    if smoke is not None:
        s += 15 if smoke >= .65 else 8 if smoke >= .30 else 0
    s += 25 if hotspots and hotspots > 0 else 0
    s = min(s, 100)
    return s, risk_level(s)
