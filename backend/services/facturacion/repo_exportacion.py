"""services.facturacion.repo_exportacion — DAL para la tabla `facturas_exportacion`.

Paralelo a `repo.py` — misma disciplina (NUNCA DELETE, anulación = Nota de Crédito, DAL psycopg3
%s style). Tabla SEPARADA de `facturas` (ver `database/schema.py` — el receptor de exportación no
tiene doc_tipo/doc_nro/condicion_iva_receptor argentinos). Sin `pedido_id`: flujo nuevo, sin pedido
de `alquileres` de por medio (confirmado con el dueño)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional


@dataclass
class FacturaExportacion:
    id: int
    emisor: str
    ambiente: str
    cbte_tipo: int
    pto_vta: int
    cbte_nro: Optional[int]
    cae: Optional[str]
    cae_vto: Optional[date]
    receptor_razon_social: str
    receptor_pais_destino: int
    receptor_domicilio: Optional[str]
    receptor_id_impositivo: Optional[str]
    incoterm: str
    permiso_embarque: Optional[str]
    moneda: str
    cotizacion: Decimal
    imp_total: Decimal
    estado: str
    nota_credito_de: Optional[int]
    raw_request: Optional[dict]
    raw_response: Optional[dict]
    errores: Optional[list]
    fecha_emision: Optional[datetime]
    created_at: datetime
    created_by: Optional[str]


def _row_to_factura_exportacion(row: dict) -> FacturaExportacion:
    return FacturaExportacion(
        id=row["id"],
        emisor=row["emisor"],
        ambiente=row["ambiente"],
        cbte_tipo=row["cbte_tipo"],
        pto_vta=row["pto_vta"],
        cbte_nro=row["cbte_nro"],
        cae=row["cae"],
        cae_vto=row["cae_vto"],
        receptor_razon_social=row["receptor_razon_social"],
        receptor_pais_destino=row["receptor_pais_destino"],
        receptor_domicilio=row["receptor_domicilio"],
        receptor_id_impositivo=row["receptor_id_impositivo"],
        incoterm=row["incoterm"],
        permiso_embarque=row["permiso_embarque"],
        moneda=row["moneda"],
        cotizacion=row["cotizacion"],
        imp_total=row["imp_total"],
        estado=row["estado"],
        nota_credito_de=row["nota_credito_de"],
        raw_request=row["raw_request"],
        raw_response=row["raw_response"],
        errores=row["errores"],
        fecha_emision=row["fecha_emision"],
        created_at=row["created_at"],
        created_by=row["created_by"],
    )


# ---------------------------------------------------------------------------
# Lecturas
# ---------------------------------------------------------------------------


def get_by_id(factura_id: int, conn) -> Optional[FacturaExportacion]:
    row = conn.execute(
        "SELECT * FROM facturas_exportacion WHERE id = %s", (factura_id,)
    ).fetchone()
    return _row_to_factura_exportacion(row) if row else None


def list_facturas_exportacion(
    conn,
    *,
    emisor: Optional[str] = None,
    estado: Optional[str] = None,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> list[FacturaExportacion]:
    clauses = []
    params: list[Any] = []

    if emisor:
        clauses.append("emisor = %s")
        params.append(emisor)
    if estado:
        clauses.append("estado = %s")
        params.append(estado)
    if desde:
        clauses.append("fecha_emision >= %s")
        params.append(desde)
    if hasta:
        clauses.append("fecha_emision < (%s::date + interval '1 day')")
        params.append(hasta)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params += [limit, offset]

    rows = conn.execute(
        f"SELECT * FROM facturas_exportacion {where} ORDER BY created_at DESC LIMIT %s OFFSET %s",
        params,
    ).fetchall()
    return [_row_to_factura_exportacion(r) for r in rows]


# ---------------------------------------------------------------------------
# Escrituras
# ---------------------------------------------------------------------------


def insert_factura_exportacion(
    *,
    conn,
    emisor: str,
    ambiente: str,
    cbte_tipo: int,
    pto_vta: int,
    receptor_razon_social: str,
    receptor_pais_destino: int,
    incoterm: str,
    moneda: str,
    cotizacion: Decimal,
    imp_total: Decimal,
    receptor_domicilio: Optional[str] = None,
    receptor_id_impositivo: Optional[str] = None,
    permiso_embarque: Optional[str] = None,
    raw_request: Optional[dict] = None,
    created_by: Optional[str] = None,
) -> int:
    """Inserta una Factura de Exportación en estado 'pendiente'. Devuelve el id."""
    row = conn.execute(
        """
        INSERT INTO facturas_exportacion (
            emisor, ambiente, cbte_tipo, pto_vta,
            receptor_razon_social, receptor_pais_destino, receptor_domicilio,
            receptor_id_impositivo, incoterm, permiso_embarque,
            moneda, cotizacion, imp_total,
            raw_request, estado, created_by
        ) VALUES (
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, 'pendiente', %s
        )
        RETURNING id
        """,
        (
            emisor, ambiente, cbte_tipo, pto_vta,
            receptor_razon_social, receptor_pais_destino, receptor_domicilio,
            receptor_id_impositivo, incoterm, permiso_embarque,
            moneda, cotizacion, imp_total,
            json.dumps(raw_request) if raw_request else None,
            created_by,
        ),
    ).fetchone()
    return row["id"]


def update_cae_exportacion(
    factura_id: int,
    conn,
    *,
    cbte_nro: int,
    cae: str,
    cae_vto: date,
    raw_response: dict,
    estado: str = "emitida",
) -> None:
    """Actualiza el CAE de exportación recibido de ARCA. Estado pasa a 'emitida' (o 'error')."""
    conn.execute(
        """
        UPDATE facturas_exportacion
           SET cbte_nro = %s, cae = %s, cae_vto = %s,
               raw_response = %s, estado = %s, fecha_emision = now()
         WHERE id = %s
        """,
        (cbte_nro, cae, cae_vto, json.dumps(raw_response), estado, factura_id),
    )


def update_error_exportacion(
    factura_id: int,
    conn,
    *,
    errores: list,
    raw_response: Optional[dict] = None,
) -> None:
    """Marca la Factura de Exportación como 'error' con detalle de errores."""
    conn.execute(
        """
        UPDATE facturas_exportacion
           SET estado = 'error', errores = %s, raw_response = %s
         WHERE id = %s
        """,
        (json.dumps(errores), json.dumps(raw_response) if raw_response else None, factura_id),
    )


def marcar_anulada(factura_id: int, conn) -> None:
    """Marca la Factura de Exportación original como 'anulada' (su CAE sigue válido; la NC es la
    anulación) — mismo criterio que `repo.marcar_anulada`."""
    conn.execute(
        "UPDATE facturas_exportacion SET estado = 'anulada' WHERE id = %s",
        (factura_id,),
    )


def revertir_anulacion(factura_id: int, conn) -> None:
    """Vuelve la Factura de Exportación original a 'emitida' si la NC que la iba a anular falló
    ante ARCA."""
    conn.execute(
        "UPDATE facturas_exportacion SET estado = 'emitida' WHERE id = %s",
        (factura_id,),
    )
