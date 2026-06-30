"""services.facturacion.engine — orquestador de emisión de facturas ARCA.

Implementa la secuencia robusta de `emitir_factura` y `emitir_nota_credito`:
- Advisory lock por (pto_vta, cbte_tipo) durante TODA la llamada SOAP
- Idempotencia via UNIQUE parcial + FECompConsultar ante timeout
- TX atómica para persistir CAE; PDF en best-effort fuera de la TX
- Nunca 500: error ARCA → estado='error', reintentable

Reglas invariantes (no violar):
- Nunca DELETE de una factura emitida
- No toca el core de reservas
- Secretos solo en ENV (gating default-deny)
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Optional

from database import get_db, now_ar

from arca_fe import (
    CaeResult,
    CbteTipo,
    CondicionIva,
    Emisor,
    armar_fecae,
    tipo_comprobante,
    calcular_importes,
    armar_qr,
    CbteAsoc,
)
from services.facturacion.config import credenciales
from services.facturacion.emisores import emisor_para
from services.facturacion.wsaa_cache import get_ta
from services.facturacion.comprobante_pedido import construir_comprobante
from services.facturacion.repo import (
    Factura,
    get_factura_vigente,
    get_by_id,
    insert_factura,
    update_cae,
    update_error,
    update_pdf_key,
    marcar_anulada,
)
from arca_fe.wsfe import WsfeClient

logger = logging.getLogger(__name__)

# Namespace de advisory lock para facturas (≠ pedidos, que usan el suyo)
_LOCK_NS = 0xFA0C0000


def _advisory_hash(pto_vta: int, cbte_tipo: int) -> int:
    """Número de lock deterministico para (pto_vta, cbte_tipo)."""
    key = f"{pto_vta}:{cbte_tipo}"
    h = int(hashlib.sha256(key.encode()).hexdigest(), 16) & 0x7FFFFFFF
    return (_LOCK_NS | (h & 0xFFFF)) & 0x7FFFFFFF


def _get_pedido(conn, pedido_id: int) -> dict:
    from database import row_to_dict
    from routes.alquileres import (
        _enriquecer_pedido_con_cliente_fiscal,
        _enriquecer_pedido_con_total,
        _enriquecer_pedido_con_cliente,
        _batch_get_alquiler_items,
    )

    row = conn.execute(
        "SELECT * FROM alquileres WHERE id = %s",
        (pedido_id,),
    ).fetchone()
    if not row:
        raise ValueError(f"Pedido {pedido_id} no encontrado")
    pedido = row_to_dict(row)

    # Cargar items (necesarios para _enriquecer_pedido_con_total)
    items_map = _batch_get_alquiler_items(conn, [pedido_id])
    pedido["items"] = items_map.get(pedido_id, [])

    _enriquecer_pedido_con_total(conn, pedido)
    _enriquecer_pedido_con_cliente_fiscal(conn, pedido)
    _enriquecer_pedido_con_cliente(conn, pedido)
    return pedido


# ---------------------------------------------------------------------------
# Emisión de factura
# ---------------------------------------------------------------------------


def emitir_factura(pedido_id: int, *, emitido_por: Optional[str] = None) -> Factura:
    """Emite o devuelve la factura vigente para el pedido.

    Secuencia (orden OBLIGATORIO):
    1. Validar estado del pedido ≥ 'confirmado'
    2. Resolver emisor + datos fiscales del receptor
    3. Construir ComprobanteRequest
    4. Advisory lock por (pto_vta, cbte_tipo) — se mantiene hasta el commit
    5. Idempotencia: si ya hay factura vigente, devolverla
    6. INSERT estado='pendiente' ANTES de llamar al WS
    7. FECompConsultar del último número (por si hubo timeout en request anterior)
    8. FECAESolicitar; persistir CAE+número en TX ATÓMICA
    9. Error ARCA → estado='error', nunca 500
    10. PDF en best-effort fuera de la TX fiscal
    """
    with get_db() as conn:
        pedido = _get_pedido(conn, pedido_id)

        estado = (pedido.get("estado") or "").lower()
        if estado not in ("confirmado", "retirado", "devuelto", "finalizado"):
            raise ValueError(
                f"El pedido {pedido_id} está en estado '{estado}'; "
                "solo se puede facturar desde 'confirmado' o posterior"
            )

        perfil_receptor = (pedido.get("cliente_perfil_impuestos") or "").strip().lower()
        nombre_emisor = emisor_para(perfil_receptor, conn)
        cred = credenciales(nombre_emisor, conn)

        emisor_obj = Emisor(
            cuit=cred.cuit,
            punto_venta=cred.punto_venta,
            condicion_iva=(
                CondicionIva.RESPONSABLE_INSCRIPTO
                if cred.condicion_iva == "responsable_inscripto"
                else CondicionIva.MONOTRIBUTO
            ),
        )

        hoy = now_ar().date()
        req = construir_comprobante(pedido, emisor_obj, emisor_obj.condicion_iva, fecha=hoy)
        cbte_tipo = tipo_comprobante(req)
        importes = calcular_importes(req)

        lock_n = _advisory_hash(emisor_obj.punto_venta, int(cbte_tipo))
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (lock_n,))

        # 5. Idempotencia
        vigente = get_factura_vigente(pedido_id, conn)
        if vigente and vigente.estado == "emitida":
            return vigente

        # 6. Persistir pendiente
        doc_tipo = int(req.receptor.doc_tipo)
        doc_nro = str(req.receptor.doc_nro)
        cond_iva_rec = int(req.receptor.condicion_iva)
        neto_int = int(importes["neto"] * 100)   # céntimos no — ARCA trabaja en ARS enteros
        # ARCA usa valores en pesos con 2 decimales pero los almacenamos en centavos? No.
        # La tabla usa "enteros ARS" = pesos sin centavos (igual que alquiler_pagos)
        # calcular_importes devuelve Decimal("1234.56") → int(1234.56) = 1234 (trunca)
        # Para preservar los 2 decimales: multiplicamos por 100 y guardamos centavos? No,
        # la tabla no tiene esa convención. Usamos round() en enteros de pesos.
        neto_int = int(round(float(importes["neto"])))
        iva_int = int(round(float(importes["iva"])))
        total_int = int(round(float(importes["total"])))

        cuit_rec = pedido.get("cliente_cuit") or ""
        razon_social = pedido.get("cliente_razon_social") or pedido.get("cliente_nombre") or ""

        if vigente:
            factura_id = vigente.id
        else:
            factura_id = insert_factura(
                conn=conn,
                pedido_id=pedido_id,
                emisor=nombre_emisor,
                ambiente=cred.ambiente,
                cbte_tipo=int(cbte_tipo),
                pto_vta=emisor_obj.punto_venta,
                doc_tipo=doc_tipo,
                doc_nro=doc_nro,
                condicion_iva_receptor=cond_iva_rec,
                concepto=int(req.concepto),
                imp_neto=neto_int,
                imp_iva=iva_int,
                imp_total=total_int,
                moneda="PES",
                cliente_cuit=cuit_rec or None,
                razon_social=razon_social or None,
                raw_request={"cbte_tipo": int(cbte_tipo), "concepto": int(req.concepto)},
                created_by=emitido_por,
            )

        # 7-8. SOAP (mantenemos el lock durante la llamada)
        token, sign = get_ta(nombre_emisor, conn)
        wsfe = WsfeClient(
            endpoint=cred.endpoint_wsfe,
            cuit=cred.cuit,
            token=token,
            sign=sign,
        )

        ultimo = wsfe.ultimo_autorizado(emisor_obj.punto_venta, int(cbte_tipo))

        # Revisar si el último número ya tiene un CAE (idempotencia post-timeout)
        numero_a_emitir = ultimo + 1
        recuperado: Optional[CaeResult] = None
        if ultimo > 0:
            consultado = wsfe.consultar(emisor_obj.punto_venta, int(cbte_tipo), ultimo)
            if consultado and (consultado.get("Resultado") or "R") == "A":
                # Puede que sea de una factura anterior (no nuestra)
                cae_consulta = consultado.get("CodAutorizacion")
                if cae_consulta:
                    vto_raw = consultado.get("CAEFchVto", "")
                    from arca_fe.wsfe import _parse_fecha
                    recuperado = CaeResult(
                        resultado="A",
                        cae=str(cae_consulta),
                        cae_vto=_parse_fecha(vto_raw),
                        numero=ultimo,
                    )
                    numero_a_emitir = ultimo

        cae_result: Optional[CaeResult] = recuperado
        if cae_result is None:
            fecae_payload = armar_fecae(req, numero_a_emitir)
            cae_result = wsfe.solicitar_cae(fecae_payload)

        # 8. TX atómica: persistir CAE
        if cae_result.resultado == "A" and cae_result.cae:
            qr_url = armar_qr(
                cuit_emisor=cred.cuit,
                pto_vta=emisor_obj.punto_venta,
                cbte_tipo=int(cbte_tipo),
                nro_cmp=cae_result.numero,
                importe_total=importes["total"],
                doc_tipo_rec=doc_tipo,
                doc_nro_rec=int(doc_nro) if doc_nro.isdigit() else 0,
                cae=cae_result.cae,
                fecha=hoy,
            )
            update_cae(
                factura_id,
                conn,
                cbte_nro=cae_result.numero,
                cae=cae_result.cae,
                cae_vto=cae_result.cae_vto,
                qr_payload=qr_url,
                raw_response={
                    "resultado": cae_result.resultado,
                    "cae": cae_result.cae,
                    "cae_vto": str(cae_result.cae_vto),
                    "observaciones": list(cae_result.observaciones),
                },
                estado="emitida",
            )
        else:
            update_error(
                factura_id,
                conn,
                errores=list(cae_result.errores) + list(cae_result.observaciones),
                raw_response={
                    "resultado": cae_result.resultado,
                    "errores": list(cae_result.errores),
                    "observaciones": list(cae_result.observaciones),
                },
            )

    # Leer la factura ya actualizada (fuera de la TX)
    with get_db() as conn:
        factura = get_by_id(factura_id, conn)

    if factura is None:
        raise RuntimeError(f"factura_id={factura_id} desapareció tras commit")

    # 10. Best-effort: PDF → R2
    if factura.estado == "emitida":
        _generar_pdf_background(factura, pedido)

    return factura


def _generar_pdf_background(factura: Factura, pedido: dict) -> None:
    """Genera el PDF y lo sube a R2 (best-effort, no lanza si falla)."""
    try:
        from services.facturacion.pdf import factura_html
        from pdf import _render_pdf

        html_str = factura_html(factura, pedido)
        pdf_bytes = asyncio.get_event_loop().run_until_complete(_render_pdf(html_str))

        from services.media.storage import put
        key = f"facturas/{factura.pedido_id}/{factura.cbte_nro or factura.id}.pdf"
        put(key, pdf_bytes, "application/pdf")

        with get_db() as conn:
            update_pdf_key(factura.id, conn, pdf_key=key)
            factura.pdf_key = key
    except Exception:
        logger.exception("PDF de factura %d falló (best-effort, no crítico)", factura.id)


# ---------------------------------------------------------------------------
# Nota de crédito
# ---------------------------------------------------------------------------


def emitir_nota_credito(
    factura_id: int, *, emitido_por: Optional[str] = None
) -> Factura:
    """Emite una Nota de Crédito que referencia `factura_id` y la anula.

    La factura original pasa a estado='anulada'. Su CAE sigue válido; la
    anulación ante ARCA es la NC emitida.
    """
    with get_db() as conn:
        original = get_by_id(factura_id, conn)
        if original is None:
            raise ValueError(f"Factura {factura_id} no encontrada")
        if original.estado != "emitida":
            raise ValueError(
                f"La factura {factura_id} está en estado '{original.estado}'; "
                "solo se pueden anular facturas emitidas"
            )

        # Verificar que no haya una NC vigente ya
        nc_existente = conn.execute(
            """SELECT id FROM facturas
               WHERE nota_credito_de = %s AND estado IN ('pendiente','emitida')""",
            (factura_id,),
        ).fetchone()
        if nc_existente:
            return get_by_id(nc_existente["id"], conn)

        pedido = _get_pedido(conn, original.pedido_id)
        nombre_emisor = original.emisor
        cred = credenciales(nombre_emisor, conn)

        emisor_obj = Emisor(
            cuit=cred.cuit,
            punto_venta=original.pto_vta,
            condicion_iva=(
                CondicionIva.RESPONSABLE_INSCRIPTO
                if cred.condicion_iva == "responsable_inscripto"
                else CondicionIva.MONOTRIBUTO
            ),
        )

        cbte_orig = CbteTipo(original.cbte_tipo)
        cbte_asoc = CbteAsoc(
            tipo=cbte_orig,
            punto_venta=original.pto_vta,
            numero=original.cbte_nro,
            cuit=cred.cuit,
            fecha=original.fecha_emision.date() if original.fecha_emision else None,
        )

        hoy = now_ar().date()
        req = construir_comprobante(
            pedido,
            emisor_obj,
            emisor_obj.condicion_iva,
            fecha=hoy,
            es_nota_credito=True,
            cbtes_asoc=(cbte_asoc,),
        )
        cbte_tipo_nc = tipo_comprobante(req)
        importes = calcular_importes(req)

        lock_n = _advisory_hash(emisor_obj.punto_venta, int(cbte_tipo_nc))
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (lock_n,))

        neto_int = int(round(float(importes["neto"])))
        iva_int = int(round(float(importes["iva"])))
        total_int = int(round(float(importes["total"])))

        nc_id = insert_factura(
            conn=conn,
            pedido_id=original.pedido_id,
            emisor=nombre_emisor,
            ambiente=cred.ambiente,
            cbte_tipo=int(cbte_tipo_nc),
            pto_vta=emisor_obj.punto_venta,
            doc_tipo=original.doc_tipo,
            doc_nro=original.doc_nro,
            condicion_iva_receptor=original.condicion_iva_receptor,
            concepto=original.concepto,
            imp_neto=neto_int,
            imp_iva=iva_int,
            imp_total=total_int,
            moneda="PES",
            cliente_cuit=original.cliente_cuit,
            razon_social=original.razon_social,
            raw_request={"nota_credito_de": factura_id, "cbte_tipo": int(cbte_tipo_nc)},
            created_by=emitido_por,
        )
        # Actualizar FK nota_credito_de
        conn.execute(
            "UPDATE facturas SET nota_credito_de = %s WHERE id = %s",
            (factura_id, nc_id),
        )

        token, sign = get_ta(nombre_emisor, conn)
        wsfe = WsfeClient(
            endpoint=cred.endpoint_wsfe,
            cuit=cred.cuit,
            token=token,
            sign=sign,
        )

        ultimo = wsfe.ultimo_autorizado(emisor_obj.punto_venta, int(cbte_tipo_nc))
        fecae = armar_fecae(req, ultimo + 1)
        cae_result = wsfe.solicitar_cae(fecae)

        if cae_result.resultado == "A" and cae_result.cae:
            qr_url = armar_qr(
                cuit_emisor=cred.cuit,
                pto_vta=emisor_obj.punto_venta,
                cbte_tipo=int(cbte_tipo_nc),
                nro_cmp=cae_result.numero,
                importe_total=importes["total"],
                doc_tipo_rec=original.doc_tipo,
                doc_nro_rec=int(original.doc_nro) if original.doc_nro.isdigit() else 0,
                cae=cae_result.cae,
                fecha=hoy,
            )
            update_cae(
                nc_id, conn,
                cbte_nro=cae_result.numero,
                cae=cae_result.cae,
                cae_vto=cae_result.cae_vto,
                qr_payload=qr_url,
                raw_response={"resultado": "A", "cae": cae_result.cae},
                estado="emitida",
            )
            marcar_anulada(factura_id, conn)
        else:
            update_error(
                nc_id, conn,
                errores=list(cae_result.errores),
                raw_response={"resultado": cae_result.resultado, "errores": list(cae_result.errores)},
            )

    with get_db() as conn:
        return get_by_id(nc_id, conn)
