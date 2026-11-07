"""Bot de Telegram: avisos + /confirm ID y /false ID (misma transicion que la API)."""
from __future__ import annotations
import logging
import requests
from .engine import AlertAlreadyDecided, AlertNotFound

log = logging.getLogger("sat.telegram")
HELP = ("Comandos:\n/alerts - alertas pendientes\n/status - resumen de riesgo\n"
        "/confirm ID - confirmar alerta\n/false ID - falsa alarma\n/id - tu chat_id")


class TelegramBot:
    def __init__(self, settings, engine):
        self.s, self.engine = settings, engine
        self.allowed = {str(c) for c in settings.telegram_chat_ids}
        self.last_error = None

    @property
    def enabled(self):
        return bool(self.s.telegram_token)

    def _call(self, method, _http=35, **params):
        r = requests.post(f"https://api.telegram.org/bot{self.s.telegram_token}/{method}",
                          json=params, timeout=_http)
        r.raise_for_status()
        return r.json()

    def send(self, chat_id, text):
        if not self.enabled:
            return
        try:
            self._call("sendMessage", _http=10, chat_id=chat_id, text=text)
        except Exception as e:
            self.last_error = str(e)[:200]
            log.warning("Telegram sendMessage fallo: %s", e)

    def broadcast(self, text):
        for cid in self.allowed:
            self.send(cid, text)

    # callbacks del Engine
    def notify_alert(self, a):
        tag = "DEMO" if a["source_mode"] == "DEMO" else "LIVE"
        self.broadcast(f"ALERTA DE INCENDIO #{a['id']} [{tag}]\nNodo: {a['node_id']}\n"
                       f"Riesgo: {a['risk_score']}/100\nEstado: {a['status']}\n"
                       f"Responde /confirm {a['id']} o /false {a['id']}")

    def notify_decision(self, a):
        self.broadcast(f"Alerta #{a['id']} ({a['node_id']}) -> {a['status']} por {a['confirmed_by']}")

    # recepcion
    def handle_update(self, upd):
        msg = upd.get("message") or {}
        text = (msg.get("text") or "").strip()
        if not text.startswith("/"):
            return
        chat_id = str(msg["chat"]["id"])
        cmd, *args = text.split()
        cmd = cmd.split("@")[0].lower()
        if cmd == "/id":
            return self.send(chat_id, f"Tu chat_id es {chat_id}")
        if chat_id not in self.allowed:
            log.warning("Chat no autorizado: %s", chat_id)
            return self.send(chat_id, "No autorizado. Pide que agreguen tu chat_id a TELEGRAM_CHAT_IDS.")
        if cmd in ("/start", "/help"):
            return self.send(chat_id, HELP)
        if cmd == "/status":
            o = self.engine.overview()
            return self.send(chat_id, f"Riesgo {o['risk_score']}/100 ({o['risk_level']}) - "
                                      f"focos: {o['active_hotspots']} - fuente: {o['source_mode']}")
        if cmd == "/alerts":
            p = self.engine.list_alerts(status="PENDING")
            return self.send(chat_id, "\n".join(f"#{a['id']} {a['node_id']} {a['risk_score']}/100"
                                                for a in p) or "Sin alertas pendientes")
        if cmd in ("/confirm", "/false"):
            if not args or not args[0].isdigit():
                return self.send(chat_id, f"Uso: {cmd} ID")
            status = "CONFIRMED" if cmd == "/confirm" else "FALSE_ALARM"
            try:  # el mensaje de exito lo envia notify_decision
                self.engine.transition_alert(int(args[0]), status, f"telegram:{chat_id}")
            except AlertNotFound:
                self.send(chat_id, f"La alerta #{args[0]} no existe")
            except AlertAlreadyDecided as e:
                self.send(chat_id, f"La alerta #{args[0]} ya estaba {e.alert['status']}")
            return
        self.send(chat_id, HELP)

    def run_forever(self, stop):
        if not self.enabled:
            return
        offset = None
        try:  # ignora comandos viejos acumulados
            res = self._call("getUpdates", _http=15, offset=-1, limit=1).get("result", [])
            if res:
                offset = res[-1]["update_id"] + 1
        except Exception as e:
            log.warning("Telegram getUpdates inicial fallo: %s", e)
        while not stop.is_set():
            try:
                data = self._call("getUpdates", _http=35, offset=offset, timeout=25)
            except Exception as e:
                self.last_error = str(e)[:200]
                stop.wait(5)
                continue
            for upd in data.get("result", []):
                offset = upd["update_id"] + 1
                try:
                    self.handle_update(upd)
                except Exception:
                    log.exception("error procesando update")
