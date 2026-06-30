"""arca_fe.qr — armado del QR fiscal (RG4892).

Sin estado, sin IO, sin imports de backend.*
"""
from __future__ import annotations

import base64
import json
from datetime import date
from decimal import Decimal


def armar_qr(
    *,
    cuit_emisor: int,
    pto_vta: int,
    cbte_tipo: int,
    nro_cmp: int,
    importe_total: Decimal,
    doc_tipo_rec: int,
    doc_nro_rec: int,
    cae: str,
    fecha: date,
    moneda: str = "PES",
    ctz: int = 1,
    ver: int = 1,
) -> str:
    """Genera la URL del QR fiscal según RG4892.

    El payload JSON se codifica en base64 (estándar, con padding) y se agrega
    como parámetro `p` de la URL canónica de AFIP/ARCA.

    Retorna la URL completa lista para incrustar como QR o como data-uri en el PDF.
    """
    payload = {
        "ver": ver,
        "fecha": fecha.strftime("%Y-%m-%d"),
        "cuit": cuit_emisor,
        "ptoVta": pto_vta,
        "tipoCmp": cbte_tipo,
        "nroCmp": nro_cmp,
        "importe": float(importe_total.quantize(Decimal("0.01"))),
        "moneda": moneda,
        "ctz": ctz,
        "tipoDocRec": doc_tipo_rec,
        "nroDocRec": doc_nro_rec,
        "tipoCodAut": "E",  # E = CAE
        "codAut": int(cae),
    }
    json_bytes = json.dumps(payload, separators=(",", ":")).encode()
    b64 = base64.b64encode(json_bytes).decode()
    return f"https://www.afip.gob.ar/fe/qr/?p={b64}"
