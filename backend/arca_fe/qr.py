"""arca_fe.qr — armado del QR fiscal (RG4892).

Sin estado, sin IO, sin imports de backend.*
"""
from __future__ import annotations

import base64
import io
import json
import re
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
    ctz: Decimal | int = 1,
    ver: int = 1,
) -> str:
    """Genera la URL del QR fiscal según RG4892 — el que AFIP exige imprimir en todo comprobante
    electrónico, para que cualquiera pueda validarlo escaneándolo desde el celular.

    `cuit_emisor`: CUIT (sin guiones) del emisor del comprobante.
    `pto_vta`/`cbte_tipo`/`nro_cmp`: mismos valores que se usaron para pedir el CAE
    (`FeCabReq.PtoVta`/`CbteTipo`, `FECAEDetRequest.CbteDesde`).
    `importe_total`: el `ImpTotal` YA AUTORIZADO por AFIP (el de `calcular_importes`/`CaeResult`,
    no un valor recalculado aparte — el QR tiene que decir exactamente lo que AFIP autorizó).
    `doc_tipo_rec`/`doc_nro_rec`: `DocTipo`/`doc_nro` del receptor (mismos códigos que
    `Receptor` — acá como `int` crudo, no el enum, porque este módulo no depende de `modelos.py`).
    `cae`: el CAE recibido de AFIP (string numérico).
    `fecha`: fecha del comprobante (`CbteFch`).
    `moneda`: código `MonId` (default `"PES"`, el caso común).
    `ctz`: cotización (`MonCotiz`) — default `1` (pesos). Acepta `int` (el caso común, pesos) o
    `Decimal` (moneda extranjera, ej. USD, casi siempre con decimales reales) — pasá un `Decimal`
    si tu cotización tiene fracción; nunca la trunques vos antes de llamar (esta función ya no
    asume que `ctz` siempre es entero).
    `ver`: versión del esquema del QR (RG4892 v1, no cambió desde que se publicó la norma).

    El payload JSON se codifica en base64 (estándar, con padding) y se agrega como parámetro `p`
    de la URL canónica de AFIP/ARCA.

    Retorna la URL completa lista para incrustar como QR (ver `qr_svg` para renderizarla como SVG
    inline) o como data-uri en el PDF."""
    payload = {
        "ver": ver,
        "fecha": fecha.strftime("%Y-%m-%d"),
        "cuit": cuit_emisor,
        "ptoVta": pto_vta,
        "tipoCmp": cbte_tipo,
        "nroCmp": nro_cmp,
        "importe": float(importe_total.quantize(Decimal("0.01"))),
        "moneda": moneda,
        "ctz": float(ctz) if isinstance(ctz, Decimal) else ctz,
        "tipoDocRec": doc_tipo_rec,
        "nroDocRec": doc_nro_rec,
        "tipoCodAut": "E",  # E = CAE
        "codAut": int(cae),
    }
    json_bytes = json.dumps(payload, separators=(",", ":")).encode()
    b64 = base64.b64encode(json_bytes).decode()
    return f"https://www.afip.gob.ar/fe/qr/?p={b64}"


def qr_svg(url: str, size: int) -> str:
    """SVG inline de un QR (pensado para el QR fiscal RG4892, pero sirve para cualquier `url`) —
    vectorial, sin resolución nativa fija: a diferencia de un PNG (se veía pixelado al hacer zoom o
    pasar por la compresión de WhatsApp), un SVG escala sin perder nitidez en NINGÚN zoom, y
    Playwright lo preserva como vector al exportar a PDF (mismo mecanismo que el logo ARCA
    embebido). Requiere el extra `qr` (`pip install arca-fe[qr]`, agrega `segno`) — import lazy,
    no hace falta si tu integración no necesita el QR como imagen standalone.

    `size` fija el width/height de display en px; el viewBox preserva la proporción del dibujo
    interno (segno no emite viewBox por default). `ImportError` si `segno` no está instalado;
    `RuntimeError` si genera un SVG sin las dimensiones esperadas — nunca devuelve un QR a medias."""
    import segno
    qr = segno.make(url, error="M")
    buf = io.BytesIO()
    qr.save(buf, kind="svg", scale=1, border=2, xmldecl=False)
    svg = buf.getvalue().decode("utf-8")

    m = re.search(r'width="(\d+)" height="(\d+)"', svg)
    if not m:
        raise RuntimeError("segno no generó un SVG con las dimensiones esperadas")
    native_w, native_h = m.group(1), m.group(2)
    return svg.replace(
        f'width="{native_w}" height="{native_h}"',
        f'viewBox="0 0 {native_w} {native_h}" width="{size}" height="{size}" role="img" aria-label="QR AFIP"',
        1,
    )
