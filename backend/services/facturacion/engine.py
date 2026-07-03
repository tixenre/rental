"""services.facturacion.engine — orquestador de emisión de facturas ARCA.

Implementa la secuencia robusta de `emitir_factura` y `emitir_nota_credito`:
- Advisory lock por (pto_vta, cbte_tipo) durante TODA la llamada SOAP
- Idempotencia via UNIQUE parcial + FECompConsultar ante timeout
- TX atómica para persistir CAE
- Nunca 500: error ARCA → estado='error', reintentable

El PDF NO se genera ni se guarda acá: se renderiza al vuelo cuando hace
falta verlo/descargarlo/mandarlo por mail (`routes/facturacion.py`), a
partir de los datos ya persistidos — la factura no cambia una vez emitida,
así que regenerar el PDF siempre da el mismo resultado.

Reglas invariantes (no violar):
- Nunca DELETE de una factura emitida
- No toca el core de reservas
- Secretos solo en ENV (gating default-deny)
"""

from __future__ import annotations

import hashlib
from typing import Optional

from database import get_db, now_ar

from arca_fe import (
    ArcaError,
    CaeResult,
    CbteTipo,
    CondicionIva,
    DocTipo,
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
from services.facturacion.comprobante_pedido import (
    construir_comprobante,
    construir_comprobante_nc,
)
from services.facturacion.repo import (
    Factura,
    get_factura_vigente,
    get_by_id,
    insert_factura,
    update_cae,
    update_error,
    marcar_anulada,
    revertir_anulacion,
)
from arca_fe.wsfe import WsfeClient

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
# Preview — arma el comprobante sin tocar ARCA (para confirmar antes de emitir)
# ---------------------------------------------------------------------------


def _chequeos_previos(
    req, perfil_receptor: str, importes: dict, ambiente: str, numero_a_emitir: int
) -> list[dict]:
    """Chequeos fail-not-fast (todos corren, ninguno frena a los demás — mismo
    patrón que `services/checkout/validar.py`). Lo irreversible es "Confirmar
    y emitir": acá se junta todo lo verificable de antemano para que ese paso
    no tenga sorpresas."""
    from identity.anchor import cuil_valido

    chequeos = [
        {
            "check": "credenciales_arca",
            "ok": True,
            "bloqueante": False,
            "mensaje": f"Conectado a ARCA ({ambiente}) — próximo comprobante N° {numero_a_emitir}",
        },
    ]

    if req.receptor.doc_tipo == DocTipo.CUIT:
        cuit_ok = cuil_valido(str(req.receptor.doc_nro))
        chequeos.append(
            {
                "check": "cuit_receptor",
                "ok": cuit_ok,
                "bloqueante": True,
                "mensaje": (
                    "CUIT del receptor con dígito verificador válido"
                    if cuit_ok
                    else f"CUIT del receptor ({req.receptor.doc_nro}) tiene el dígito verificador mal — ARCA lo va a rechazar"
                ),
            }
        )

    ri_degradado = (
        perfil_receptor == "responsable_inscripto"
        and req.receptor.condicion_iva != CondicionIva.RESPONSABLE_INSCRIPTO
    )
    chequeos.append(
        {
            "check": "perfil_fiscal_receptor",
            "ok": not ri_degradado,
            "bloqueante": False,
            "mensaje": (
                "El cliente es Responsable Inscripto pero no tiene un CUIT válido cargado — "
                "se va a facturar como Consumidor Final en vez de Factura A"
                if ri_degradado
                else "Perfil fiscal del receptor consistente"
            ),
        }
    )

    # total == neto + iva (arca_fe.comprobante.calcular_importes) y el IVA nunca
    # cambia el signo, así que chequear el total (la cifra que ve el admin) o
    # el neto da lo mismo matemáticamente — se muestra el total para no meter
    # jerga fiscal ("neto") en un chequeo pensado para el dueño, no para AFIP.
    total_ok = importes["total"] > 0
    chequeos.append(
        {
            "check": "importe_positivo",
            "ok": total_ok,
            "bloqueante": True,
            "mensaje": "Importe total positivo"
            if total_ok
            else "El importe total es $0 o negativo",
        }
    )

    fechas_ok = (
        req.fecha_serv_desde is None
        or req.fecha_serv_hasta is None
        or req.fecha_serv_desde <= req.fecha_serv_hasta
    )
    chequeos.append(
        {
            "check": "fechas_servicio",
            "ok": fechas_ok,
            "bloqueante": True,
            "mensaje": (
                "Fechas de servicio coherentes"
                if fechas_ok
                else "La fecha de inicio del servicio es posterior a la de fin"
            ),
        }
    )

    return chequeos


def previsualizar_factura(pedido_id: int, conn) -> dict:
    """Arma el `ComprobanteRequest`, calcula sus importes, y consulta a ARCA
    el próximo número de comprobante — SIN pedir CAE.

    Corre los mismos pasos 1-3 de `emitir_factura` (validar estado, resolver
    emisor/receptor, construir el comprobante) y agrega UNA llamada SOAP de
    solo lectura (`FECompUltimoAutorizado`, la misma que ya usa el paso 7 de
    la emisión real): no crea ni modifica nada en ARCA, pero sirve para dos
    cosas — mostrar el número real que le va a tocar al comprobante, y
    validar que el certificado/las credenciales funcionan ANTES de
    comprometerse a pedir un CAE real (irreversible salvo Nota de Crédito).
    Nada de advisory lock, nada de INSERT — eso sigue siendo exclusivo de
    `emitir_factura`."""
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

    # Único llamado a ARCA del preview: de solo lectura, no pide CAE. Si el
    # cert está vencido o ARCA no responde, mejor enterarse acá (RuntimeError
    # → 503) que después de que el admin ya confirmó.
    try:
        token, sign = get_ta(nombre_emisor, conn)
        wsfe = WsfeClient(
            endpoint=cred.endpoint_wsfe,
            cuit=cred.cuit,
            token=token,
            sign=sign,
        )
        ultimo = wsfe.ultimo_autorizado(emisor_obj.punto_venta, int(cbte_tipo))
    except (RuntimeError, ValueError):
        raise
    except ArcaError as exc:
        raise RuntimeError(str(exc)) from exc
    numero_a_emitir = ultimo + 1

    chequeos = _chequeos_previos(
        req, perfil_receptor, importes, cred.ambiente, numero_a_emitir
    )
    listo = all(c["ok"] or not c["bloqueante"] for c in chequeos)

    from services.facturacion.pdf import _CBTE_TIPO_LABEL

    return {
        "ambiente": cred.ambiente,
        "emisor": {
            "nombre": nombre_emisor,
            "cuit": cred.cuit,
            "condicion_iva": cred.condicion_iva,
        },
        "receptor": {
            "doc_tipo": req.receptor.doc_tipo.name,
            "doc_nro": str(req.receptor.doc_nro),
            "condicion_iva": req.receptor.condicion_iva.name.lower(),
            "razon_social": pedido.get("cliente_razon_social")
            or pedido.get("cliente_nombre")
            or "",
        },
        "comprobante": {
            "letra": _CBTE_TIPO_LABEL.get(int(cbte_tipo), "?"),
            "tipo_nro": int(cbte_tipo),
            "numero_a_emitir": numero_a_emitir,
            "pto_vta": emisor_obj.punto_venta,
        },
        "importes": {
            "neto": float(importes["neto"]),
            "iva": float(importes["iva"]),
            "total": float(importes["total"]),
        },
        "fechas": {
            "emision": hoy.isoformat(),
            "servicio_desde": req.fecha_serv_desde.isoformat()
            if req.fecha_serv_desde
            else None,
            "servicio_hasta": req.fecha_serv_hasta.isoformat()
            if req.fecha_serv_hasta
            else None,
            "vto_pago": req.fecha_vto_pago.isoformat() if req.fecha_vto_pago else None,
        },
        "chequeos": chequeos,
        "listo": listo,
    }


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
        req = construir_comprobante(
            pedido, emisor_obj, emisor_obj.condicion_iva, fecha=hoy
        )
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
        # La tabla usa "enteros ARS" = pesos sin centavos (igual que alquiler_pagos).
        neto_int = int(round(float(importes["neto"])))
        iva_int = int(round(float(importes["iva"])))
        total_int = int(round(float(importes["total"])))

        cuit_rec = pedido.get("cliente_cuit") or ""
        razon_social = (
            pedido.get("cliente_razon_social") or pedido.get("cliente_nombre") or ""
        )

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
                raw_request={
                    "cbte_tipo": int(cbte_tipo),
                    "concepto": int(req.concepto),
                },
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

        try:
            ultimo = wsfe.ultimo_autorizado(emisor_obj.punto_venta, int(cbte_tipo))
            numero_a_emitir = ultimo + 1

            # Idempotencia post-timeout: si un intento anterior de ESTE pedido ya
            # le pidió a ARCA el número `numero_a_emitir` y la respuesta se perdió
            # por timeout de nuestro lado, ARCA ya lo tiene autorizado → lo
            # recuperamos en vez de pedir un CAE nuevo (evitaría "comprobante ya
            # autorizado"). Consultamos el PRÓXIMO número, no el último ya
            # autorizado — `ultimo` por definición siempre devuelve Resultado='A'
            # (no es nuestro, es el de la factura previa) y reusarlo duplicaría
            # número+CAE entre pedidos distintos (bug encontrado en prod).
            recuperado: Optional[CaeResult] = None
            consultado = wsfe.consultar(
                emisor_obj.punto_venta, int(cbte_tipo), numero_a_emitir
            )
            if consultado and (consultado.get("Resultado") or "R") == "A":
                cae_consulta = consultado.get("CodAutorizacion")
                if cae_consulta:
                    vto_raw = consultado.get("CAEFchVto", "")
                    from arca_fe.wsfe import _parse_fecha

                    recuperado = CaeResult(
                        resultado="A",
                        cae=str(cae_consulta),
                        cae_vto=_parse_fecha(vto_raw),
                        numero=numero_a_emitir,
                    )

            cae_result: Optional[CaeResult] = recuperado
            if cae_result is None:
                fecae_payload = armar_fecae(req, numero_a_emitir)
                cae_result = wsfe.solicitar_cae(fecae_payload)
        except (RuntimeError, ValueError):
            raise
        except ArcaError as exc:
            # Taxonomía tipada del motor → aplanada a RuntimeError (convención
            # del adapter, que el route mapea a 503), preservando el mensaje.
            raise RuntimeError(str(exc)) from exc
        except Exception as exc:
            # Falla de red/SOAP no controlada (invariante "nunca 500" del módulo):
            # la TX nunca llegó a commitear (nada quedó en 'pendiente' zombie).
            raise RuntimeError(
                f"Error al comunicarse con WSFEv1 ({cred.endpoint_wsfe}): "
                f"{type(exc).__name__}: {exc}"
            ) from exc

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
        conn.commit()

    # Leer la factura ya actualizada (fuera de la TX)
    with get_db() as conn:
        factura = get_by_id(factura_id, conn)

    if factura is None:
        raise RuntimeError(f"factura_id={factura_id} desapareció tras commit")

    return factura


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
        req = construir_comprobante_nc(
            original,
            pedido,
            emisor_obj,
            fecha=hoy,
            cbtes_asoc=(cbte_asoc,),
        )
        cbte_tipo_nc = tipo_comprobante(req)
        importes = calcular_importes(req)

        lock_n = _advisory_hash(emisor_obj.punto_venta, int(cbte_tipo_nc))
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (lock_n,))

        neto_int = int(round(float(importes["neto"])))
        iva_int = int(round(float(importes["iva"])))
        total_int = int(round(float(importes["total"])))

        # Anular la original ANTES de insertar la NC: el índice único parcial
        # uq_factura_vigente_por_pedido permite una sola fila 'pendiente'/'emitida'
        # por pedido — insertar la NC (pendiente) mientras la original sigue
        # 'emitida' viola ese índice. Si ARCA rechaza la NC más abajo, se revierte.
        marcar_anulada(factura_id, conn)

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

        try:
            ultimo = wsfe.ultimo_autorizado(emisor_obj.punto_venta, int(cbte_tipo_nc))
            numero_a_emitir = ultimo + 1

            # Misma idempotencia post-timeout que emitir_factura (consultar el
            # PRÓXIMO número, nunca el último ya autorizado — ver comentario ahí).
            recuperado: Optional[CaeResult] = None
            consultado = wsfe.consultar(
                emisor_obj.punto_venta, int(cbte_tipo_nc), numero_a_emitir
            )
            if consultado and (consultado.get("Resultado") or "R") == "A":
                cae_consulta = consultado.get("CodAutorizacion")
                if cae_consulta:
                    vto_raw = consultado.get("CAEFchVto", "")
                    from arca_fe.wsfe import _parse_fecha

                    recuperado = CaeResult(
                        resultado="A",
                        cae=str(cae_consulta),
                        cae_vto=_parse_fecha(vto_raw),
                        numero=numero_a_emitir,
                    )

            cae_result: Optional[CaeResult] = recuperado
            if cae_result is None:
                fecae = armar_fecae(req, numero_a_emitir)
                cae_result = wsfe.solicitar_cae(fecae)
        except (RuntimeError, ValueError):
            raise
        except ArcaError as exc:
            raise RuntimeError(str(exc)) from exc
        except Exception as exc:
            raise RuntimeError(
                f"Error al comunicarse con WSFEv1 ({cred.endpoint_wsfe}): "
                f"{type(exc).__name__}: {exc}"
            ) from exc

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
                nc_id,
                conn,
                cbte_nro=cae_result.numero,
                cae=cae_result.cae,
                cae_vto=cae_result.cae_vto,
                qr_payload=qr_url,
                raw_response={"resultado": "A", "cae": cae_result.cae},
                estado="emitida",
            )
        else:
            update_error(
                nc_id,
                conn,
                errores=list(cae_result.errores),
                raw_response={
                    "resultado": cae_result.resultado,
                    "errores": list(cae_result.errores),
                },
            )
            # ARCA rechazó la NC: la original nunca se anuló de verdad, revertir.
            revertir_anulacion(factura_id, conn)
        conn.commit()

    with get_db() as conn:
        return get_by_id(nc_id, conn)
