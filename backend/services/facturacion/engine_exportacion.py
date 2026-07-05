"""services.facturacion.engine_exportacion — orquestador de emisión de Facturas de Exportación
(WSFEXv1).

Módulo NUEVO, no una extensión de `engine.py` (menos acoplamiento — son dos dominios de AFIP
distintos). Mismo esqueleto robusto que `emitir_factura`:
- Advisory lock por (pto_vta, cbte_tipo) durante TODA la llamada SOAP
- Idempotencia vía FEXGetLast_CMP/FEXGetCMP (mismo patrón que WSFEv1)
- TX atómica para persistir CAE
- Nunca 500: error ARCA → estado='error', reintentable

Sin `pedido_id`/receptor argentino: la Factura de Exportación es un flujo NUEVO, sin depender de
`alquileres` (confirmado con el dueño) — el caller (route admin) arma el `ComprobanteExportacionRequest`
completo a partir de datos cargados a mano, no de un pedido existente. Por eso tampoco hay
verificación contra el padrón de ARCA (`verificar_y_actualizar_receptor`): el receptor no es
argentino, no tiene CUIT que verificar contra la Consulta de Constancia de Inscripción.

Reglas invariantes (no violar, mismas que `engine.py`):
- Nunca DELETE de una factura emitida
- No toca el core de reservas (no aplica: este módulo ni siquiera toca `alquileres`)
- Secretos solo en ENV (gating default-deny, vía `config.credenciales`)
"""
from __future__ import annotations

import hashlib
from typing import Optional

from database import get_db

from arca_fe import ArcaError, CaeResult, armar_qr
from arca_fe.modelos_exportacion import ComprobanteExportacionRequest
from arca_fe.comprobante_exportacion import tipo_comprobante_exportacion
from arca_fe.wsfex import WsfexClient, WSFEX_WSAA_SERVICIO
from services.facturacion.config import credenciales
from services.facturacion.emisores_repo import get_by_nombre
from services.facturacion.wsaa_cache import get_ta
from services.facturacion.repo_exportacion import (
    FacturaExportacion,
    get_by_id,
    insert_factura_exportacion,
    update_cae_exportacion,
    update_error_exportacion,
    marcar_anulada,
    revertir_anulacion,
)

# Namespace de advisory lock PROPIO — distinto de `engine._LOCK_NS` (facturas domésticas) y de
# cualquier otro namespace ya usado en el repo (pedidos, contabilidad, reportes) para no colisionar
# con locks de otro dominio.
_LOCK_NS = 0xFA0D0000


def _advisory_hash(pto_vta: int, cbte_tipo: int) -> int:
    """Número de lock deterministico para (pto_vta, cbte_tipo) — mismo algoritmo que
    `engine._advisory_hash`, namespace distinto."""
    key = f"{pto_vta}:{cbte_tipo}"
    h = int(hashlib.sha256(key.encode()).hexdigest(), 16) & 0x7FFFFFFF
    return (_LOCK_NS | (h & 0xFFFF)) & 0x7FFFFFFF


def emitir_factura_exportacion(
    nombre_emisor: str,
    comprobante: ComprobanteExportacionRequest,
    *,
    emitido_por: Optional[str] = None,
) -> FacturaExportacion:
    """Emite una Factura de Exportación para `comprobante` a nombre de `nombre_emisor`.

    Secuencia (orden OBLIGATORIO, mismo criterio que `engine.emitir_factura`):
    1. Resolver credenciales del emisor + confirmar que está habilitado para exportación
       (`emisores_arca.habilitado_exportacion` — falla temprano con mensaje claro, no un
       ArcaAuthError críptico contra AFIP).
    2. Advisory lock por (pto_vta, cbte_tipo) — se mantiene hasta el commit.
    3. INSERT estado='pendiente' ANTES de llamar al WS.
    4. FEXGetLast_CMP del último número (por si hubo timeout en un intento anterior).
    5. FEXAuthorize; persistir CAE+número en TX ATÓMICA.
    6. Error ARCA → estado='error', nunca 500.
    """
    with get_db() as conn:
        emisor_row = get_by_nombre(nombre_emisor, conn)
        if emisor_row is None:
            raise ValueError(f"Emisor '{nombre_emisor}' no encontrado.")
        if not emisor_row.habilitado_exportacion:
            raise ValueError(
                f"El emisor '{nombre_emisor}' no está habilitado para exportación — delegá el "
                "servicio de Comprobantes de Exportación en el Administrador de Relaciones de "
                "Clave Fiscal de AFIP y marcalo en el back-office → Facturación ARCA → Emisores."
            )

        cred = credenciales(nombre_emisor, conn)
        cbte_tipo = tipo_comprobante_exportacion(comprobante)

        lock_n = _advisory_hash(comprobante.emisor.punto_venta, int(cbte_tipo))
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (lock_n,))

        factura_id = insert_factura_exportacion(
            conn=conn,
            emisor=nombre_emisor,
            ambiente=cred.ambiente,
            cbte_tipo=int(cbte_tipo),
            pto_vta=comprobante.emisor.punto_venta,
            receptor_razon_social=comprobante.receptor.razon_social,
            receptor_pais_destino=comprobante.receptor.pais_destino_id,
            receptor_domicilio=comprobante.receptor.domicilio or None,
            receptor_id_impositivo=comprobante.receptor.id_impositivo or None,
            incoterm=comprobante.exportacion.incoterm,
            permiso_embarque=comprobante.exportacion.permiso_embarque or None,
            moneda=comprobante.moneda,
            cotizacion=comprobante.cotizacion,
            imp_total=comprobante.importe_neto,
            raw_request={
                "cbte_tipo": int(cbte_tipo),
                "pais_destino": comprobante.receptor.pais_destino_id,
            },
            created_by=emitido_por,
        )

        token, sign = get_ta(nombre_emisor, conn, servicio=WSFEX_WSAA_SERVICIO)
        wsfex = WsfexClient(
            endpoint=cred.endpoint_wsfex,
            cuit=cred.cuit,
            token=token,
            sign=sign,
        )

        try:
            ultimo = wsfex.ultimo_autorizado(comprobante.emisor.punto_venta, int(cbte_tipo))
            numero_a_emitir = ultimo + 1

            # Idempotencia post-timeout — mismo criterio que engine.py: consultamos el PRÓXIMO
            # número (no el último autorizado, que por definición es de OTRA factura) por si un
            # intento anterior de ESTA factura ya lo autorizó y la respuesta se perdió acá.
            recuperado: Optional[CaeResult] = None
            consultado = wsfex.consultar(
                comprobante.emisor.punto_venta, int(cbte_tipo), numero_a_emitir
            )
            if consultado and (consultado.get("Resultado") or "R") == "A":
                cae_consulta = consultado.get("Cae")
                if cae_consulta:
                    from arca_fe import parse_fecha_arca

                    recuperado = CaeResult(
                        resultado="A",
                        cae=str(cae_consulta),
                        cae_vto=parse_fecha_arca(consultado.get("Fch_venc_Cae", "")),
                        numero=numero_a_emitir,
                    )

            cae_result: Optional[CaeResult] = recuperado
            if cae_result is None:
                cae_result = wsfex.autorizar(comprobante, numero_a_emitir)
        except (RuntimeError, ValueError, ArcaError):
            # Mismo criterio que engine.py: el route elige el status HTTP por subtipo, no un 503
            # genérico. La fila 'pendiente' queda para reintentar (no se borra).
            raise
        except Exception as exc:
            raise RuntimeError(
                f"Error al comunicarse con WSFEXv1 ({cred.endpoint_wsfex}): "
                f"{type(exc).__name__}: {exc}"
            ) from exc

        if cae_result.resultado == "A" and cae_result.cae:
            # Receptor exterior sin CUIT argentino: sin un DocTipo real de AFIP para este caso, se
            # usa la convención 99/0 ("Doc. (Otro)"/sin identificar) — tentativo, a confirmar contra
            # el manual de RG4892 aplicado a WSFEXv1 (mismo criterio de honestidad que el resto del
            # módulo: no se asume, se marca explícito).
            qr_url = armar_qr(
                cuit_emisor=cred.cuit,
                pto_vta=comprobante.emisor.punto_venta,
                cbte_tipo=int(cbte_tipo),
                nro_cmp=cae_result.numero,
                importe_total=comprobante.importe_neto,
                doc_tipo_rec=99,
                doc_nro_rec=0,
                cae=cae_result.cae,
                fecha=comprobante.fecha,
                moneda=comprobante.moneda,
                ctz=comprobante.cotizacion,
            )
            update_cae_exportacion(
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
            update_error_exportacion(
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

    with get_db() as conn:
        factura = get_by_id(factura_id, conn)

    if factura is None:
        raise RuntimeError(f"factura_id={factura_id} desapareció tras commit")

    return factura


def emitir_nota_credito_exportacion(
    factura_id: int,
    comprobante_nc: ComprobanteExportacionRequest,
    *,
    emitido_por: Optional[str] = None,
) -> FacturaExportacion:
    """Emite una Nota de Crédito de exportación que referencia `factura_id` y la anula.

    `comprobante_nc` tiene que tener `es_nota_credito=True` y `cbtes_asoc` apuntando a la factura
    original (validado por `ComprobanteExportacionRequest.__post_init__`) — mismo criterio que
    `engine.emitir_nota_credito`: la factura original pasa a 'anulada' (su CAE sigue válido) antes
    de que la NC pase a 'emitida', en la MISMA transacción."""
    with get_db() as conn:
        original = get_by_id(factura_id, conn)
        if original is None:
            raise ValueError(f"Factura de exportación {factura_id} no encontrada.")
        if original.estado != "emitida":
            raise ValueError(
                f"Solo se puede anular una Factura de Exportación 'emitida' (está en "
                f"'{original.estado}')."
            )
        if not comprobante_nc.es_nota_credito:
            raise ValueError("comprobante_nc tiene que tener es_nota_credito=True.")

        marcar_anulada(factura_id, conn)
        conn.commit()

    try:
        nc = emitir_factura_exportacion(original.emisor, comprobante_nc, emitido_por=emitido_por)
    except Exception:
        with get_db() as conn:
            revertir_anulacion(factura_id, conn)
            conn.commit()
        raise

    with get_db() as conn:
        conn.execute(
            "UPDATE facturas_exportacion SET nota_credito_de = %s WHERE id = %s",
            (factura_id, nc.id),
        )
        conn.commit()

    with get_db() as conn:
        return get_by_id(nc.id, conn)
