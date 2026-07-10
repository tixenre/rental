"""services.facturacion.comprobante_render — arma un `arca_fe.ComprobanteFiscal` a partir de
`Factura` + `pedido` y delega el render en `arca_fe.render.renderizar_comprobante_html`.

Todo lo que es contenido/estructura fiscal (los 3 layouts, el logo de ARCA, la leyenda de
Transparencia Fiscal, el formato del comprobante) vive en `arca_fe` — este módulo solo resuelve lo
que la librería portable no puede resolver sola: catálogos de AFIP cacheados en Postgres
(`services.facturacion.catalogos`, requieren `conn`), datos de negocio del emisor/pedido
(razón social, domicilio, condición de venta) y las fuentes propias de Rambla (vendoreadas,
inyectadas como `fonts_css`, nunca hardcodeadas en la librería).
"""
from __future__ import annotations

import os
from functools import lru_cache

import arca_fe
from arca_fe import CondicionIva, DocTipo, ItemFactura, Receptor

# `condicion_iva` del EMISOR es un string propio de `emisores_arca`
# (_CONDICIONES_VALIDAS en emisores_repo.py) — vocabulario NUESTRO (no de ARCA), tabla distinta a
# la del receptor (códigos numéricos de ARCA, `label_condicion_iva_receptor` en
# `services.facturacion.catalogos`). Solo hace falta el LABEL de texto (`ComprobanteFiscal` no
# recibe la condición IVA del emisor como enum — el CUIT/condición del emisor son datos de
# configuración aparte, no fiscales del comprobante ya validado, ver docstring de ComprobanteFiscal).
_EMISOR_COND_IVA_LABEL: dict[str, str] = {
    "responsable_inscripto": "IVA Responsable Inscripto",
    "monotributo": "Responsable Monotributo",
    "exento": "IVA Exento",
}


def emisor_condicion_iva_label(condicion_iva: str) -> str:
    """Label de la condición IVA del EMISOR para mostrar (ej. en el preview de "Confirmar
    factura", `services.facturacion.engine.previsualizar_factura`) — mismo texto que va impreso
    en la factura ya emitida. Único punto público sobre `_EMISOR_COND_IVA_LABEL`."""
    return _EMISOR_COND_IVA_LABEL.get(condicion_iva, "—")


_EMISOR_ROW_CAMPOS = ("razon_social", "cuit", "condicion_iva", "domicilio", "iibb", "inicio_actividades")


def _emisor_row(nombre: str, conn) -> dict:
    """Lee los datos legales del emisor desde `emisores_arca` — administrables desde el
    back-office, NUNCA hardcodeados por nombre (un emisor nuevo heredaba en silencio los datos de
    "santini" antes de este fix). Si la fila no existe (emisor mal configurado/renombrado), cae a
    todo vacío — `arca_fe.render` degrada esos campos a "—", nunca rompe el render.

    Reusa `conn` (no abre su propia conexión) — `_armar_comprobante_fiscal` la comparte con los 3
    lookups de catálogo, una sola conexión por render en vez de 4."""
    try:
        row = conn.execute(
            "SELECT razon_social, cuit, condicion_iva, domicilio, iibb, inicio_actividades "
            "FROM emisores_arca WHERE nombre = %s",
            (nombre,),
        ).fetchone()
        if row:
            return {campo: row[campo] or "" for campo in _EMISOR_ROW_CAMPOS}
    except Exception:
        pass
    return {campo: "" for campo in _EMISOR_ROW_CAMPOS}


# ---------------------------------------------------------------------------
# Fuentes propias (TT Commons + JetBrains Mono, vendoreadas — mismas que usa la web), inyectadas a
# `arca_fe.render.renderizar_comprobante_html(..., fonts_css=...)`. Playwright renderiza con base
# `about:blank`: todo va embebido, nada de `<img src="archivo-relativo">`.
#
# El nombre de familia CSS declarado acá es 'ComprobanteSans' — el nombre LÓGICO que
# `arca_fe.render` usa en sus templates (nunca 'TT Commons' hardcodeado ahí, que sería la marca
# de Rambla filtrándose a una librería agnóstica de marca). Esto es puro re-etiquetado de los
# mismos bytes de TT Commons — cero cambio visual en las facturas reales de Rambla; simplemente
# arca_fe ahora también tiene su propio default (Inter) bajo ese mismo nombre lógico para quien no
# pase su propio `fonts_css` (ver docs/DECISIONES.md → "Tema tipográfico compartido de arca_fe").
# ---------------------------------------------------------------------------

_FONTS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "frontend", "public", "fonts", "woff2"
)
_FONT_FILES = [
    ("tt-commons-400.woff2", "ComprobanteSans", 400),
    ("tt-commons-500.woff2", "ComprobanteSans", 500),
    ("tt-commons-600.woff2", "ComprobanteSans", 600),
    ("tt-commons-700.woff2", "ComprobanteSans", 700),
    ("tt-commons-800.woff2", "ComprobanteSans", 800),
    ("jetbrains-mono-400.woff2", "JetBrains Mono", 400),
    ("jetbrains-mono-500.woff2", "JetBrains Mono", 500),
]


@lru_cache(maxsize=1)
def _fonts_css() -> str:
    import base64

    faces = []
    for fname, family, weight in _FONT_FILES:
        path = os.path.join(_FONTS_DIR, fname)
        try:
            with open(path, "rb") as fh:
                b64 = base64.b64encode(fh.read()).decode("ascii")
        except OSError:
            continue
        faces.append(
            f"@font-face{{font-family:'{family}';font-weight:{weight};"
            f"font-style:normal;font-display:swap;"
            f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}"
        )
    return "<style>" + "".join(faces) + "</style>"


# Default de Rambla: el concepto facturado es una sola línea "Rambla #N" (el número del pedido),
# sin desglose por equipo ni texto adicional — decisión de negocio, no un requisito de ARCA (WSFE
# solo pide los importes agregados; el desglose por ítem es puramente de presentación). El nombre
# es configurable (`FACTURACION_CONCEPTO_MARCA`) para que otro negocio que reuse este motor pueda
# poner el suyo en vez de "Rambla".
CONCEPTO_MARCA = os.getenv("FACTURACION_CONCEPTO_MARCA", "Rambla")


def _conceptos(pedido: dict, imp_neto) -> tuple[ItemFactura, ...]:
    """Ítem único del comprobante: `"{CONCEPTO_MARCA} #{numero_pedido}"`, sin desglose por equipo
    — ver `CONCEPTO_MARCA`. Recibe `imp_neto` directo (no el objeto `Factura` completo) para que
    también lo pueda usar un preview PRE-emisión (`engine.previsualizar_factura_html`), que
    todavía no tiene una fila `Factura` persistida."""
    numero = pedido.get("numero_pedido") or pedido.get("id", "")
    return (
        ItemFactura(
            codigo="001",
            descripcion=f"{CONCEPTO_MARCA} #{numero}",
            precio_unitario=imp_neto,
            subtotal=imp_neto,
        ),
    )


def _armar_comprobante_fiscal(factura, pedido: dict) -> "arca_fe.ComprobanteFiscal":
    """Resuelve lo que `arca_fe` no puede resolver solo: labels de catálogo y datos de negocio del
    emisor/pedido. Una sola conexión para los 4 lookups (emisor + 3 catálogos) — antes cada uno
    abría/cerraba la suya (4 round-trips de conexión por render, sin ninguna razón para no
    compartirla dentro de la misma función síncrona)."""
    from database import get_db
    from services.facturacion.catalogos import (
        label_concepto,
        label_condicion_iva_receptor,
        label_doc_tipo,
    )

    conn = get_db()
    try:
        em_row = _emisor_row(factura.emisor, conn)
        doc_label = label_doc_tipo(factura.doc_tipo, conn)
        concepto_label = label_concepto(factura.concepto, conn)
        cond_iva_receptor_label = label_condicion_iva_receptor(factura.condicion_iva_receptor, conn)
    finally:
        conn.close()

    em_cond_label = _EMISOR_COND_IVA_LABEL.get(em_row["condicion_iva"], "—")

    doc_nro_raw = factura.cliente_cuit or factura.doc_nro or "0"

    # `venta`/`vencimiento_pago` son default de NEGOCIO de Rambla (alquiler cobrado antes/al
    # inicio), no un requisito de ARCA — igual que `CONCEPTO_MARCA` arriba, otro negocio que reuse
    # este adapter puede resolverlos distinto (ej. venta a plazo real con vencimiento propio del
    # pedido) sin tocar `arca_fe` (`ComprobanteFiscal.condicion_venta`/`vencimiento_pago` son
    # strings/fechas libres, no un enum cerrado).
    total_pedido = pedido.get("monto_total")
    pagado = pedido.get("monto_pagado") or 0
    venta = "Contado" if total_pedido is None or pagado >= total_pedido else "Cuenta corriente"

    # No hay campo de vencimiento comercial propio en el pedido: por default de negocio (alquiler
    # se abona antes/al inicio) se usa la fecha de inicio.
    fecha_desde = pedido.get("fecha_desde")

    return arca_fe.ComprobanteFiscal(
        cbte_tipo=factura.cbte_tipo,
        pto_vta=factura.pto_vta,
        numero=factura.cbte_nro or 0,
        fecha_emision=factura.fecha_emision,
        cae=factura.cae or "",
        cae_vto=factura.cae_vto,
        qr_url=factura.qr_payload or "",
        receptor=Receptor(
            doc_tipo=DocTipo(factura.doc_tipo),
            doc_nro=doc_nro_raw,
            condicion_iva=CondicionIva(factura.condicion_iva_receptor),
        ),
        receptor_nombre=factura.razon_social or pedido.get("cliente_nombre") or "—",
        concepto_label=concepto_label,
        doc_tipo_label=doc_label,
        condicion_iva_receptor_label=cond_iva_receptor_label,
        emisor_condicion_iva_label=em_cond_label,
        items=_conceptos(pedido, factura.imp_neto),
        importe_neto=factura.imp_neto,
        importe_iva=factura.imp_iva,
        importe_total=factura.imp_total,
        emisor_cuit=em_row["cuit"],
        emisor_razon_social=em_row["razon_social"] or "—",
        emisor_domicilio=em_row["domicilio"],
        emisor_iibb=em_row["iibb"],
        emisor_inicio_actividades=em_row["inicio_actividades"] or None,
        # `factura.domicilio` queda FIJO al emitir (verificado contra el padrón de ARCA) — a
        # diferencia de antes, que se leía en vivo de la ficha del cliente en cada reimpresión y
        # podía "cambiar" retroactivamente. Facturas emitidas antes de esta columna (NULL) caen al
        # valor en vivo de siempre (backward-compatible).
        receptor_domicilio=factura.domicilio or pedido.get("cliente_domicilio_fiscal") or "—",
        condicion_venta=venta,
        periodo_desde=fecha_desde,
        periodo_hasta=pedido.get("fecha_hasta"),
        vencimiento_pago=fecha_desde,
    )


def factura_html(factura, pedido: dict, layout: str = "simplificada") -> str:
    """Genera el HTML completo de la factura (Factura A/B/C o Nota de Crédito).

    `factura` es una instancia de `services.facturacion.repo.Factura`. `pedido` viene de
    `services.facturacion.engine._get_pedido` (items + cliente enriquecidos). `layout`:
    'simplificada' (default de Rambla, compacta 4:5, mínimo 1080×1350 — NO admite desglose de
    cantidad/precio unitario) · 'oficial' (réplica AFIP/ARCA, A4) · 'detallada' (A4, identidad de
    la simplificada pero con el detalle completo). Ver `arca_fe.LAYOUTS_INFO` para la descripción
    completa de cada uno, pensada para mostrarse al usuario que elige."""
    datos = _armar_comprobante_fiscal(factura, pedido)
    return arca_fe.render.renderizar_comprobante_html(datos, layout=layout, fonts_css=_fonts_css())


def factura_filename(factura, *, layout: str = "simplificada") -> str:
    """Nombre de archivo canónico del PDF de una factura/NC (admin + portal cliente).

    Sin sufijo para el layout DEFAULT de Rambla (simplificada, 4:5); los demás layouts (pedidos
    explícitamente) llevan su nombre como sufijo."""
    prefijo = "NC" if arca_fe.es_nota_credito(factura.cbte_tipo) else "Factura"
    sufijo = "" if layout == "simplificada" else f"-{layout}"
    nombre_fiscal = arca_fe.render.nombre_fiscal_comprobante(
        factura.cbte_tipo, factura.pto_vta, factura.cbte_nro or 0
    )
    return f"{prefijo}-{nombre_fiscal}{sufijo}.pdf"
