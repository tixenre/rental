"""services.facturacion.comprobante_render_exportacion — arma un
`arca_fe.ComprobanteFiscalExportacion` a partir de una `FacturaExportacion` y delega el render en
`arca_fe.renderizar_factura_exportacion_html`.

Paralelo a `comprobante_render.py` (WSFEv1) — mismo criterio: todo lo que es contenido/estructura
fiscal vive en `arca_fe`, este módulo solo resuelve lo que la librería portable no puede sola
(catálogo de países destino cacheado en Postgres, datos de negocio del emisor). Sin `pedido`: la
Factura de Exportación es un flujo sin pedido de por medio (ver `engine_exportacion.py`)."""
from __future__ import annotations

import os

import arca_fe
from arca_fe import ItemFactura

from services.facturacion.comprobante_render import _emisor_row, _EMISOR_COND_IVA_LABEL

# Mismo default de negocio que `comprobante_render.CONCEPTO_MARCA` — configurable para que otro
# negocio que reuse este motor ponga el suyo.
CONCEPTO_MARCA = os.getenv("FACTURACION_CONCEPTO_MARCA", "Rambla")


def _pais_destino_label(pais_id: int, conn) -> str:
    """Descripción del país destino desde el catálogo de WSFEXv1 cacheado — cae al código crudo si
    el catálogo nunca se refrescó o el id no está (nunca rompe el render de una factura ya
    emitida)."""
    from services.facturacion.catalogos_exportacion import paises_destino

    try:
        catalogo = paises_destino(conn)
    except RuntimeError:
        return str(pais_id)
    for p in catalogo:
        if p.get("id") == pais_id:
            return p.get("desc") or str(pais_id)
    return str(pais_id)


def _conceptos_exportacion(factura) -> tuple[ItemFactura, ...]:
    """Ítem único del comprobante — mismo criterio que `comprobante_render._conceptos`: sin
    desglose, un renglón con el importe total de la operación."""
    return (
        ItemFactura(
            codigo="001",
            descripcion=f"{CONCEPTO_MARCA} Exportación #{factura.id}",
            precio_unitario=factura.imp_total,
            subtotal=factura.imp_total,
        ),
    )


def _armar_comprobante_fiscal_exportacion(factura, conn) -> "arca_fe.ComprobanteFiscalExportacion":
    em_row = _emisor_row(factura.emisor, conn)
    em_cond_label = _EMISOR_COND_IVA_LABEL.get(em_row["condicion_iva"], "—")
    pais_label = _pais_destino_label(factura.receptor_pais_destino, conn)

    return arca_fe.ComprobanteFiscalExportacion(
        cbte_tipo=factura.cbte_tipo,
        pto_vta=factura.pto_vta,
        numero=factura.cbte_nro or 0,
        fecha_emision=factura.fecha_emision,
        emisor_cuit=em_row["cuit"],
        emisor_razon_social=em_row["razon_social"] or "—",
        emisor_condicion_iva_label=em_cond_label,
        emisor_domicilio=em_row["domicilio"],
        receptor_razon_social=factura.receptor_razon_social,
        receptor_pais_destino_label=pais_label,
        receptor_domicilio=factura.receptor_domicilio,
        receptor_id_impositivo=factura.receptor_id_impositivo,
        incoterm=factura.incoterm,
        permiso_embarque=factura.permiso_embarque,
        moneda=factura.moneda,
        cotizacion=factura.cotizacion,
        items=_conceptos_exportacion(factura),
        importe_total=factura.imp_total,
        cae=factura.cae or "",
        cae_vto=factura.cae_vto,
        qr_url=factura.qr_payload or "",
    )


def factura_exportacion_html(factura, conn) -> str:
    """Genera el HTML completo de la Factura/Nota de Crédito de Exportación. `factura` es una
    instancia de `services.facturacion.repo_exportacion.FacturaExportacion`."""
    datos = _armar_comprobante_fiscal_exportacion(factura, conn)
    return arca_fe.renderizar_factura_exportacion_html(datos)


def factura_exportacion_filename(factura) -> str:
    """Nombre de archivo canónico del PDF (mismo criterio que `comprobante_render.factura_filename`,
    sin variantes de layout — este documento tiene uno solo)."""
    from arca_fe.modelos_exportacion import es_nota_credito_exportacion

    prefijo = "NC-E" if es_nota_credito_exportacion(factura.cbte_tipo) else "Factura-E"
    return f"{prefijo}-{factura.pto_vta:05d}-{(factura.cbte_nro or 0):08d}.pdf"
