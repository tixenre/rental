"""services.facturacion.pdf — template HTML de la factura electrónica ARCA.

Produce una página A4 autocontenida (fonts inline) lista para Playwright → PDF.
Incluye: membrete del emisor, datos del receptor, tabla de conceptos, IVA
discriminado (Factura A) u omitido (C), QR AFIP, CAE + vencimiento, y un banner
"HOMOLOGACIÓN" si el ambiente no es producción.

Molde: `pdf_templates._contrato_html` (mismo shell, mismo DS).
"""
from __future__ import annotations

import html as _html
import os
from datetime import date
from typing import Optional

# ---------------------------------------------------------------------------
# Datos de los emisores (env o defaults razonables para homologación)
# ---------------------------------------------------------------------------

_EMISORES_DATA: dict[str, dict] = {
    "pablo": {
        "nombre": os.getenv("AFIP_PABLO_NOMBRE", "Pablo Marín"),
        "cond_iva_label": "Responsable Inscripto",
        "tipo_cbte": "FACTURA",
        "domicilio": os.getenv("AFIP_PABLO_DOMICILIO", "Mar del Plata, Buenos Aires"),
        "email": os.getenv("OWNER_EMAIL", "ramblarental@gmail.com"),
        "telefono": os.getenv("OWNER_TELEFONO", "223 590-9080"),
    },
    "santini": {
        "nombre": os.getenv("AFIP_SANTINI_NOMBRE", "Javier Santini Calarco"),
        "cond_iva_label": "Monotributo",
        "tipo_cbte": "FACTURA",
        "domicilio": os.getenv("AFIP_SANTINI_DOMICILIO", "Falucho 4625, Mar del Plata"),
        "email": os.getenv("OWNER_EMAIL", "ramblarental@gmail.com"),
        "telefono": os.getenv("OWNER_TELEFONO", "223 590-9080"),
    },
}

_CBTE_TIPO_LABEL: dict[int, str] = {
    1: "A", 3: "A", 6: "B", 8: "B", 11: "C", 13: "C",
}

_CBTE_TIPO_NOTA: dict[int, bool] = {
    3: True, 8: True, 13: True,
}


# ---------------------------------------------------------------------------
# Helpers de formato
# ---------------------------------------------------------------------------


def _ars(n: int) -> str:
    """$ 1.234.567"""
    return f"$ {int(n):,.0f}".replace(",", ".")


def _pct(p: float) -> str:
    return f"{p:.0f}%"


def _fdate(d) -> str:
    if d is None:
        return "—"
    if isinstance(d, str):
        d = d[:10]
        try:
            d = date.fromisoformat(d)
        except ValueError:
            return d
    return d.strftime("%d/%m/%Y")


def _e(s) -> str:
    return _html.escape(str(s or ""))


# ---------------------------------------------------------------------------
# CSS mínimo (hereda tokens del DS, versión inline)
# ---------------------------------------------------------------------------

_CSS = """
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'TT Commons', sans-serif; font-size: 11px;
         color: #1a1a1a; background: #fff; padding: 14mm; }
  h1 { font-size: 26px; font-weight: 900; letter-spacing: -0.5px; }
  h2 { font-size: 13px; font-weight: 700; margin-bottom: 4px; }
  table { width: 100%; border-collapse: collapse; font-size: 10.5px; }
  th { text-align: left; font-weight: 600; padding: 4px 6px;
       background: #f5f4f0; border-bottom: 1px solid #e0ddd5; }
  td { padding: 4px 6px; border-bottom: 1px solid #f0ede8; }
  .label { font-size: 9px; text-transform: uppercase; letter-spacing: .05em;
           color: #888; }
  .value { font-weight: 500; }
  .mono  { font-family: 'JetBrains Mono', monospace; }
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
  .section { margin-top: 16px; }
  .box { border: 1px solid #e0ddd5; border-radius: 6px; padding: 10px; }
  .total-row { font-size: 13px; font-weight: 700; }
  .qr-area { display: flex; align-items: flex-start; gap: 16px; margin-top: 12px; }
  .cae-data { font-size: 10px; }
  .cae-data p { margin-bottom: 2px; }
  .banner { text-align: center; font-size: 10px; font-weight: 700;
            color: #b45309; background: #fef3c7; border: 1px solid #f59e0b;
            border-radius: 4px; padding: 4px 8px; margin-bottom: 12px; }
  .leyenda { font-size: 9px; color: #888; margin-top: 6px; }
  .letra-box { display: inline-block; width: 32px; height: 32px; text-align: center;
               line-height: 32px; font-size: 18px; font-weight: 900;
               border: 2px solid #1a1a1a; border-radius: 4px; margin-right: 8px; }
  .header-top { display: flex; justify-content: space-between; align-items: flex-start; }
  .cbte-info { text-align: right; }
"""


def _google_fonts() -> str:
    return (
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">'
    )


# ---------------------------------------------------------------------------
# Builder principal
# ---------------------------------------------------------------------------


def factura_html(factura, pedido: dict) -> str:
    """Genera el HTML completo de la factura (Factura A/C o Nota de Crédito).

    `factura` es una instancia de `services.facturacion.repo.Factura`.
    `pedido` debe tener cliente_nombre, descripción de ítems, etc.
    """
    em_data = _EMISORES_DATA.get(factura.emisor, _EMISORES_DATA["santini"])
    letra = _CBTE_TIPO_LABEL.get(factura.cbte_tipo, "C")
    es_nc = _CBTE_TIPO_NOTA.get(factura.cbte_tipo, False)
    es_prod = factura.ambiente == "produccion"

    titulo = f"NOTA DE CRÉDITO {letra}" if es_nc else f"FACTURA {letra}"
    nro_fmt = f"{factura.pto_vta:05d}-{factura.cbte_nro or 0:08d}" if factura.cbte_nro else "PENDIENTE"

    # QR como <img data-uri> si hay CAE
    qr_img = ""
    if factura.qr_payload:
        try:
            from arca_fe.qr import _build_qr_image_data_uri
            qr_img = f'<img src="{_build_qr_image_data_uri(factura.qr_payload)}" width="80" height="80" alt="QR AFIP">'
        except Exception:
            qr_img = f'<span class="mono" style="font-size:8px">{_e(factura.qr_payload[:40])}…</span>'

    # Tabla de conceptos
    desc_principal = (
        pedido.get("descripcion")
        or f"Alquiler de equipos — Pedido #{pedido.get('numero_pedido') or pedido.get('id', '')}"
    )
    fecha_desde = _fdate(pedido.get("fecha_desde"))
    fecha_hasta = _fdate(pedido.get("fecha_hasta"))

    # IVA discriminado solo en A/B
    mostrar_iva = letra in ("A", "B") and factura.imp_iva > 0

    banner = ""
    if not es_prod:
        banner = '<div class="banner">⚠ COMPROBANTE DE HOMOLOGACIÓN — NO VÁLIDO FISCALMENTE</div>'

    neto_display = _ars(factura.imp_neto)
    iva_display = _ars(factura.imp_iva) if mostrar_iva else ""
    total_display = _ars(factura.imp_total)

    body = f"""
<div class="header-top">
  <div>
    <h1>rambla</h1>
    <div style="font-size:10px; color:#888; margin-top:2px">ALQUILER DE EQUIPOS AUDIOVISUALES</div>
    <div style="margin-top:8px">
      <div class="label">Emisor</div>
      <div class="value">{_e(em_data['nombre'])}</div>
      <div>{_e(em_data['cond_iva_label'])}</div>
      <div class="mono">{_e(factura.emisor == 'pablo' and pedido.get('cuit_pablo', '') or '')}</div>
      <div style="font-size:10px; color:#666">{_e(em_data['domicilio'])}</div>
    </div>
  </div>
  <div class="cbte-info">
    <div>
      <span class="letra-box">{_e(letra)}</span>
      <span style="font-size:20px; font-weight:900">{_e(titulo)}</span>
    </div>
    <div class="mono" style="font-size:14px; margin-top:4px">{_e(nro_fmt)}</div>
    <div class="label" style="margin-top:4px">Fecha de emisión</div>
    <div class="mono">{_fdate(factura.fecha_emision)}</div>
    <div class="label" style="margin-top:4px">Punto de venta</div>
    <div class="mono">{factura.pto_vta:05d}</div>
  </div>
</div>

<div class="section grid-2">
  <div class="box">
    <div class="label">Receptor</div>
    <div class="value">{_e(factura.razon_social or pedido.get('cliente_nombre') or '—')}</div>
    <div class="label" style="margin-top:4px">CUIT / Documento</div>
    <div class="mono">{_e(factura.cliente_cuit or factura.doc_nro or '—')}</div>
    <div class="label" style="margin-top:4px">Condición frente al IVA</div>
    <div>{_e(_cond_iva_label(factura.condicion_iva_receptor))}</div>
  </div>
  <div class="box">
    <div class="label">Período del servicio</div>
    <div class="mono">{_e(fecha_desde)} → {_e(fecha_hasta)}</div>
    <div class="label" style="margin-top:4px">Pedido</div>
    <div>#{_e(str(pedido.get('numero_pedido') or pedido.get('id', '—')))}</div>
  </div>
</div>

<div class="section">
  <table>
    <thead><tr>
      <th>Concepto</th>
      <th class="mono" style="text-align:right">Importe neto</th>
    </tr></thead>
    <tbody>
      <tr>
        <td>{_e(desc_principal)}</td>
        <td class="mono" style="text-align:right">{neto_display}</td>
      </tr>
{"      <tr><td class='label'>IVA 21%</td><td class='mono' style='text-align:right'>" + iva_display + "</td></tr>" if mostrar_iva else ""}
    </tbody>
    <tfoot>
      <tr class="total-row">
        <td style="border-top:2px solid #1a1a1a">TOTAL</td>
        <td class="mono" style="text-align:right; border-top:2px solid #1a1a1a; color:#FAB428">{total_display}</td>
      </tr>
    </tfoot>
  </table>
</div>

<div class="qr-area section">
  {qr_img}
  <div class="cae-data">
    <p class="label">Comprobante Autorizado por ARCA</p>
    <p><strong>CAE:</strong> <span class="mono">{_e(factura.cae or '—')}</span></p>
    <p><strong>Vto. CAE:</strong> <span class="mono">{_fdate(factura.cae_vto)}</span></p>
    <p class="leyenda">Verifique la validez de este comprobante en www.arca.gob.ar</p>
  </div>
</div>
"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width">
  {_google_fonts()}
  <style>{_CSS}</style>
</head>
<body>
{banner}
{body}
</body>
</html>"""


def _cond_iva_label(cond_int: int) -> str:
    return {
        1: "Responsable Inscripto",
        4: "Exento",
        5: "Consumidor Final",
        6: "Monotributo",
    }.get(cond_int, "—")
