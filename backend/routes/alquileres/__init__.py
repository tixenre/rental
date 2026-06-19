"""Paquete del router de alquileres (#501 — split del god-module `routes/alquileres.py`).

Superficie externa amplia: `main` importa `router`; estudio / cliente_portal /
clientes y muchos tests importan modelos, constantes y helpers internos. Este
`__init__` re-exporta esa superficie pública estable. El router es UNO solo (creado
en `core`); cada submódulo extraído registra sus rutas sobre ese mismo router al
importarse.
"""
from routes.alquileres.core import (
    router,
    # ── Modelos / constantes ──
    CotizarItem,
    CotizarRequest,
    PedidoCreate,
    PedidoDatos,
    PedidoItem,
    DESTINATARIOS_PAGO,
    METODOS_PAGO,
    ESTADOS_RESERVADO,
    # ── Endpoints consumidos como función ──
    cotizar,
    create_pedido,
    propagar_descuento_a_presupuestos,
    # ── Helpers ──
    get_db,
    _apply_pedido_datos,
    _apply_pedido_items,
    _batch_get_alquiler_items,
    _dispatch_pedido_creado_emails,
    _enriquecer_pedido_con_cliente,
    _enriquecer_pedido_con_total,
    _enriquecer_pedidos_con_cliente,
    _get_alquiler_detail,
    _get_alquiler_items,
    _ics_adjunto_pedido,
    _next_numero_pedido,
    _parse_precio,
    _pedido_email_context,
    _recalcular_total_pedido,
    _resolver_destino_metodo,
    _validar_fecha_iso,
)
# Disponibilidad + validación de horarios: endpoint y helper consumidos por
# estudio / cliente_portal / tests vía este paquete.
from routes.alquileres.disponibilidad import (
    get_disponibilidad,
    _validar_horarios_habilitados,
)
# Helpers de documentos (PDFs + mail) consumidos por los tests vía este paquete.
from routes.alquileres.documentos import (
    _agrupar_items_por_categoria,
    _ordenar_items_en_grupos,
    _cuerpo_mail_simple,
)

__all__ = [
    "router",
    "CotizarItem", "CotizarRequest", "PedidoCreate", "PedidoDatos", "PedidoItem",
    "DESTINATARIOS_PAGO", "METODOS_PAGO", "ESTADOS_RESERVADO",
    "cotizar", "create_pedido", "get_disponibilidad", "propagar_descuento_a_presupuestos",
    "get_db",
    "_agrupar_items_por_categoria", "_apply_pedido_datos", "_apply_pedido_items",
    "_batch_get_alquiler_items", "_cuerpo_mail_simple", "_dispatch_pedido_creado_emails",
    "_enriquecer_pedido_con_cliente", "_enriquecer_pedido_con_total",
    "_enriquecer_pedidos_con_cliente", "_get_alquiler_detail", "_get_alquiler_items",
    "_ics_adjunto_pedido", "_next_numero_pedido", "_ordenar_items_en_grupos",
    "_parse_precio", "_pedido_email_context", "_recalcular_total_pedido",
    "_resolver_destino_metodo", "_validar_fecha_iso", "_validar_horarios_habilitados",
]

# Submódulos sin símbolos re-exportados: el import registra sus rutas sobre el
# `router` compartido; el tuple los mantiene "usados" para ruff. (`documentos`
# sí re-exporta helpers, arriba — su import ya registra sus rutas.)
from routes.alquileres import descuentos as _descuentos

_SUBMODULOS = (_descuentos,)
