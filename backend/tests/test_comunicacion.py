"""Tests de la capa única de comunicación (registro + despachador). Sin DB/red."""
from __future__ import annotations

import services.comunicacion.despacho as d
import services.whatsapp as wa
from services.comunicacion.eventos import REGISTRO


class _FakeBG:
    def __init__(self):
        self.tasks = []

    def add_task(self, fn, *a, **k):
        self.tasks.append((fn, a, k))


# ── registro (fuente única) ──────────────────────────────────────────────
def test_registro_referencia_templates_whatsapp_reales():
    from services.whatsapp.plantillas import REGISTRO as WA

    for ev in REGISTRO.values():
        if ev.whatsapp:
            assert ev.whatsapp in WA, f"{ev.key}: template whatsapp '{ev.whatsapp}' no existe"
        assert ev.canales and all(c in ("mail", "whatsapp") for c in ev.canales)


def test_devolucion_es_solo_whatsapp():
    for k in ("recordatorio_devolucion_d1", "recordatorio_devolucion_d0", "recordatorio_devolucion_vencido"):
        ev = REGISTRO[k]
        assert ev.canales == ("whatsapp",) and ev.mail is None


# ── fan-out ──────────────────────────────────────────────────────────────
def test_creado_fanout_background(monkeypatch):
    monkeypatch.setattr(d, "send_email", lambda *a, **k: None)
    monkeypatch.setattr(d, "get_admin_to", lambda: "admin@x.com")
    monkeypatch.setattr(wa, "enviar_evento_pedido", lambda *a, **k: None)
    bg = _FakeBG()
    d.notificar_pedido(
        "pedido_creado", {"id": 1, "cliente_id": 2, "cliente_email": "c@x.com"}, {"x": 1}, background=bg
    )
    mails = [t for t in bg.tasks if t[0] is d.send_email]
    was = [t for t in bg.tasks if t[0] is wa.enviar_evento_pedido]
    assert len(mails) == 2  # cliente + admin
    assert len(was) == 1 and was[0][1][0] == "pedido_creado"


def test_creado_sync_devuelve_resultados_por_canal(monkeypatch):
    monkeypatch.setattr(d, "send_email", lambda *a, **k: {"ok": True, "to": a[1]})
    monkeypatch.setattr(d, "get_admin_to", lambda: "admin@x.com")
    monkeypatch.setattr(wa, "enviar_evento_pedido", lambda *a, **k: {"ok": True, "wamid": "W"})
    res = d.notificar_pedido("pedido_creado", {"id": 1, "cliente_id": 2, "cliente_email": "c@x.com"}, {})
    assert len(res["mail"]) == 2
    assert res["whatsapp"]["wamid"] == "W"


def test_confirmado_mail_cliente_con_ics_y_sin_admin(monkeypatch):
    enviados = []
    monkeypatch.setattr(d, "send_email", lambda *a, **k: enviados.append((a, k)) or {"ok": True})
    monkeypatch.setattr(d, "ics_adjunto_pedido", lambda p: ["ICS"])
    monkeypatch.setattr(d, "get_admin_to", lambda: "admin@x.com")  # no debería usarse
    monkeypatch.setattr(wa, "enviar_evento_pedido", lambda *a, **k: {"ok": True})
    res = d.notificar_pedido("pedido_confirmado", {"id": 1, "cliente_id": 2, "cliente_email": "c@x.com"}, {})
    assert len(res["mail"]) == 1  # solo cliente
    assert enviados[0][1].get("attachments") == ["ICS"]


def test_devolucion_solo_whatsapp_no_manda_mail(monkeypatch):
    mail_called = []
    monkeypatch.setattr(d, "send_email", lambda *a, **k: mail_called.append(a) or {"ok": True})
    monkeypatch.setattr(wa, "enviar_evento_pedido", lambda *a, **k: {"ok": True})
    res = d.notificar_pedido("recordatorio_devolucion_d1", {"id": 1, "cliente_id": 2}, {})
    assert mail_called == [] and res["mail"] == []
    assert res["whatsapp"]["ok"] is True


def test_canales_override_solo_mail(monkeypatch):
    wa_called = []
    monkeypatch.setattr(d, "send_email", lambda *a, **k: {"ok": True})
    monkeypatch.setattr(d, "get_admin_to", lambda: "")
    monkeypatch.setattr(wa, "enviar_evento_pedido", lambda *a, **k: wa_called.append(a) or {"ok": True})
    res = d.notificar_pedido(
        "pedido_creado", {"id": 1, "cliente_id": 2, "cliente_email": "c@x.com"}, {}, canales={"mail"}
    )
    assert wa_called == [] and res["whatsapp"] is None


def test_sin_email_cliente_manda_admin_y_whatsapp(monkeypatch):
    to_list = []
    monkeypatch.setattr(d, "send_email", lambda *a, **k: to_list.append(a[1]) or {"ok": True})
    monkeypatch.setattr(d, "get_admin_to", lambda: "admin@x.com")
    monkeypatch.setattr(wa, "enviar_evento_pedido", lambda *a, **k: {"ok": True})
    res = d.notificar_pedido("pedido_creado", {"id": 1, "cliente_id": 2}, {})  # sin cliente_email
    assert to_list == ["admin@x.com"]  # cliente saltado, admin sí
    assert res["whatsapp"]["ok"] is True


def test_evento_desconocido_no_rompe():
    assert d.notificar_pedido("no_existe", {"id": 1}, {}) == {"mail": [], "whatsapp": None}
