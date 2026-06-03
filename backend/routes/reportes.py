"""routes/reportes.py — Generador de reportes financieros (#88).

Liquidación por dueño: cuánto entró (pedidos 100% pagados, fechados al día en que
quedaron saldados) y cómo se reparte entre beneficiarios. La lógica vive en el
motor `backend/reportes/` — acá solo va el transporte HTTP + el CSV.
"""

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import StreamingResponse

from database import get_db
from admin_guard import require_admin
from reportes.liquidacion import liquidar

router = APIRouter()


def _validar_rango(desde: str, hasta: str) -> None:
    try:
        datetime.strptime(desde, "%Y-%m-%d")
        datetime.strptime(hasta, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(400, "Fechas inválidas — usá el formato YYYY-MM-DD.")
    if desde > hasta:
        raise HTTPException(400, "El rango es inválido: 'desde' es posterior a 'hasta'.")


def _liquidacion_csv(data: dict) -> str:
    """CSV de la liquidación: una grilla mes × beneficiario + detalle por dueño.
    Pura (testeable sin DB)."""
    buf = io.StringIO()
    w = csv.writer(buf)
    beneficiarios = data.get("beneficiarios", [])

    w.writerow(["Liquidación por mes (ingreso 100% pagado, repartido)"])
    w.writerow(["Mes", *beneficiarios, "Total"])
    for fila in data["por_mes"]:
        pb = fila["por_beneficiario"]
        w.writerow([fila["mes"], *[pb.get(b, 0) for b in beneficiarios], fila["total"]])
    res = data["resumen"]
    w.writerow(["TOTAL", *[res["por_beneficiario"].get(b, 0) for b in beneficiarios], res["total"]])

    w.writerow([])
    w.writerow(["Detalle por dueño"])
    w.writerow(["Dueño", "Equipo", "Generado (ARS)"])
    for d in data["por_dueno"]:
        for eq in d["equipos"]:
            w.writerow([d["dueno"], eq["equipo"], eq["monto"]])
        w.writerow([f"{d['dueno']} — TOTAL GENERADO", "", d["monto_generado"]])
    return buf.getvalue()


@router.get("/admin/reportes/liquidacion")
def reporte_liquidacion(
    request: Request,
    desde: str = Query(..., description="YYYY-MM-DD"),
    hasta: str = Query(..., description="YYYY-MM-DD"),
    formato: str = Query("json", description="json | csv"),
):
    require_admin(request)
    _validar_rango(desde, hasta)
    conn = get_db()
    try:
        data = liquidar(conn, desde, hasta)
    finally:
        conn.close()
    data["desde"] = desde
    data["hasta"] = hasta

    if formato == "csv":
        filename = f"liquidacion_{desde}_a_{hasta}.csv"
        return StreamingResponse(
            iter([_liquidacion_csv(data)]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    return data
