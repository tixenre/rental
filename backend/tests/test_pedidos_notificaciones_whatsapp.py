"""El shim `pedidos_notificaciones` delega en `comunicacion.notificar_pedido`.

La lógica de fan-out multi-canal se movió a `services/comunicacion/` (ver
`test_comunicacion.py`); este módulo verifica solo que la superficie de compat
siga despachando el evento correcto.
"""
from __future__ import annotations

import services.pedidos_notificaciones as pn


def test_dispatch_creado_delega_al_evento_pedido_creado(monkeypatch):
    llamadas = []
    monkeypatch.setattr(pn, "notificar_pedido", lambda ev, pedido, ctx, **k: llamadas.append((ev, k.get("background"))))
    monkeypatch.setattr(pn, "_pedido_email_context", lambda p: {"x": 1})
    pn._dispatch_pedido_creado_emails("BG", {"id": 1})
    assert llamadas == [("pedido_creado", "BG")]


def test_dispatch_confirmado_delega_al_evento_pedido_confirmado(monkeypatch):
    llamadas = []
    monkeypatch.setattr(pn, "notificar_pedido", lambda ev, pedido, ctx, **k: llamadas.append(ev))
    monkeypatch.setattr(pn, "_pedido_email_context", lambda p: {})
    pn._dispatch_pedido_confirmado(None, {"id": 1})
    assert llamadas == ["pedido_confirmado"]
