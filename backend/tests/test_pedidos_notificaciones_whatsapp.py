"""Wiring del canal WhatsApp en la boca de notificaciones de pedido (sin DB/red).

Verifica que `_dispatch_pedido_creado_emails` y `_dispatch_pedido_confirmado`
encolan el mail (como antes) Y el WhatsApp con la plantilla correcta. El envío en
sí (gating/opt-in) lo cubren los tests del adapter.
"""
from __future__ import annotations

import services.pedidos_notificaciones as pn
import services.whatsapp as wa


class _FakeBG:
    def __init__(self):
        self.tasks = []

    def add_task(self, fn, *args, **kwargs):
        self.tasks.append((fn, args, kwargs))


def _patch_comunes(monkeypatch):
    monkeypatch.setattr(pn, "_pedido_email_context", lambda p: {"ctx": True})
    monkeypatch.setattr(pn, "_ics_adjunto_pedido", lambda p: None)
    monkeypatch.setattr(pn, "get_admin_to", lambda: "admin@x.com")
    monkeypatch.setattr(pn, "send_email", lambda *a, **k: None)
    monkeypatch.setattr(wa, "enviar_evento_pedido", lambda *a, **k: None)


def _mail_tasks(bg):
    return [t for t in bg.tasks if t[0] is pn.send_email]


def _wa_tasks(bg):
    return [t for t in bg.tasks if t[0] is wa.enviar_evento_pedido]


def test_creado_encola_mail_cliente_admin_y_whatsapp(monkeypatch):
    _patch_comunes(monkeypatch)
    bg = _FakeBG()
    pedido = {"id": 7, "cliente_id": 3, "cliente_email": "c@x.com"}
    pn._dispatch_pedido_creado_emails(bg, pedido)

    assert len(_mail_tasks(bg)) == 2  # cliente + admin
    wa_t = _wa_tasks(bg)
    assert len(wa_t) == 1
    assert wa_t[0][1][0] == "pedido_creado"
    assert wa_t[0][1][1] is pedido
    assert wa_t[0][1][2] == {"ctx": True}


def test_creado_sin_email_igual_manda_whatsapp(monkeypatch):
    _patch_comunes(monkeypatch)
    monkeypatch.setattr(pn, "get_admin_to", lambda: "")  # sin admin_to tampoco
    bg = _FakeBG()
    pedido = {"id": 7, "cliente_id": 3}  # sin cliente_email
    pn._dispatch_pedido_creado_emails(bg, pedido)

    assert len(_mail_tasks(bg)) == 0
    assert len(_wa_tasks(bg)) == 1


def test_confirmado_encola_mail_y_whatsapp(monkeypatch):
    _patch_comunes(monkeypatch)
    bg = _FakeBG()
    pedido = {"id": 9, "cliente_id": 3, "cliente_email": "c@x.com"}
    pn._dispatch_pedido_confirmado(bg, pedido)

    assert len(_mail_tasks(bg)) == 1  # solo cliente
    wa_t = _wa_tasks(bg)
    assert len(wa_t) == 1
    assert wa_t[0][1][0] == "pedido_confirmado"


def test_confirmado_sin_email_manda_solo_whatsapp(monkeypatch):
    _patch_comunes(monkeypatch)
    bg = _FakeBG()
    pn._dispatch_pedido_confirmado(bg, {"id": 9, "cliente_id": 3})

    assert len(_mail_tasks(bg)) == 0
    assert len(_wa_tasks(bg)) == 1
