"""services/pedidos_notificaciones.py — shim de compatibilidad.

El armado del contexto/adjunto y el despacho multi-canal se movieron a
`services/comunicacion/` (registro de eventos + despachador — la capa única de
comunicación, decisión 2026-05-27). Este módulo se mantiene como superficie de
compatibilidad: los call sites y tests que importan `_pedido_email_context`,
`_ics_adjunto_pedido`, `_dispatch_pedido_creado_emails` y `_dispatch_pedido_confirmado`
siguen funcionando, delegando en `comunicacion`. **Código nuevo usa
`comunicacion.notificar_pedido` directo.**
"""
from __future__ import annotations

from typing import Optional

from fastapi import BackgroundTasks

from services.comunicacion import (
    ics_adjunto_pedido as _ics_adjunto_pedido,  # noqa: F401 — re-export compat
    notificar_pedido,
    pedido_email_context as _pedido_email_context,  # noqa: F401 — re-export compat
)


def _dispatch_pedido_creado_emails(background: Optional[BackgroundTasks], pedido: dict):
    """Compat: despacha el evento 'pedido creado' (mail cliente + admin + WhatsApp).
    Delega en `comunicacion.notificar_pedido`."""
    notificar_pedido("pedido_creado", pedido, _pedido_email_context(pedido), background=background)


def _dispatch_pedido_confirmado(background: Optional[BackgroundTasks], pedido: dict):
    """Compat: despacha el evento 'pedido confirmado' (mail cliente + .ics + WhatsApp).
    Delega en `comunicacion.notificar_pedido`."""
    notificar_pedido("pedido_confirmado", pedido, _pedido_email_context(pedido), background=background)
