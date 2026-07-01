"""services.facturacion.pdf — templates HTML de la factura electrónica ARCA.

Tres piezas, un mismo contexto (`_build_ctx`): **clásica** (réplica fiel del
comprobante oficial AFIP/ARCA, A4 imprimible — la que reemplaza al PDF fiscal
"de las dudas"), **celular** (comprobante vertical compacto pensado para
compartir por WhatsApp) y **formal** (A4 con la identidad visual de la
celular, alternativa prolija a la clásica). Autocontenidas (fonts + logo ARCA
inline en base64/SVG) listas para Playwright → PDF.

Diseño: handoff "Facturas Rambla" (Claude Design), alta fidelidad — colores,
tipografías, tamaños y espaciados son finales, replicados 1:1.
"""
from __future__ import annotations

import html as _html
import os
from datetime import date
from functools import lru_cache

# ---------------------------------------------------------------------------
# Datos de los emisores (env o defaults razonables para homologación).
# domicilio/IIBB/inicio de actividades son datos legales fijos por emisor —
# mismo patrón que ya regía para domicilio (env var, no hay tabla para esto).
# ---------------------------------------------------------------------------

_EMISORES_DATA: dict[str, dict] = {
    "pablo": {
        "cond_iva_label": "IVA Responsable Inscripto",
        "domicilio": os.getenv("AFIP_PABLO_DOMICILIO", "Mar del Plata, Buenos Aires"),
        # No son obligatorios para que la factura electrónica sea válida (la
        # validez la da el CAE/QR de ARCA, no estos datos) — son la
        # convención "clásica" del talonario impreso. Sin configurar → el
        # renglón entero se omite (nunca se muestra un "—" vacío).
        "iibb": os.getenv("AFIP_PABLO_IIBB", ""),
        "inicio_actividades": os.getenv("AFIP_PABLO_INICIO_ACTIVIDADES", ""),
    },
    "santini": {
        "cond_iva_label": "Responsable Monotributo",
        "domicilio": os.getenv("AFIP_SANTINI_DOMICILIO", "Falucho 4625, Mar del Plata"),
        "iibb": os.getenv("AFIP_SANTINI_IIBB", ""),
        "inicio_actividades": os.getenv("AFIP_SANTINI_INICIO_ACTIVIDADES", ""),
    },
}

# Letra + código de comprobante AFIP (`FEParamGetTiposCbte`) — el código de 2
# dígitos que va en la "caja de letra" ES el cbte_tipo, ya cero-paddeado.
_CBTE_TIPO_LABEL: dict[int, str] = {
    1: "A", 3: "A", 6: "B", 8: "B", 11: "C", 13: "C",
}
_CBTE_TIPO_NOTA: dict[int, bool] = {
    3: True, 8: True, 13: True,
}

_DOC_TIPO_LABEL: dict[int, str] = {
    80: "CUIT", 86: "CUIL", 96: "DNI", 99: "Documento",
}

_COND_IVA_LABEL: dict[int, str] = {
    1: "IVA Responsable Inscripto",
    4: "IVA Exento",
    5: "Consumidor Final",
    6: "Responsable Monotributo",
}


# ---------------------------------------------------------------------------
# Helpers de formato
# ---------------------------------------------------------------------------


def _money(n) -> str:
    """'$ 217.800,00' — 2 decimales (estándar AFIP; el comprobante fiscal
    reproduce el formato oficial, a diferencia del Presupuesto prefiscal)."""
    return "$ " + _plain(n)


def _plain(n) -> str:
    """'217.800,00' — sin símbolo, para columnas donde el $ ya está en el header."""
    entero = f"{float(n):,.2f}"
    # es-AR: punto de miles, coma decimal (toLocaleString('es-AR'))
    return entero.replace(",", "␟").replace(".", ",").replace("␟", ".")


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


def _emisor_row(nombre: str) -> dict:
    """Lee razon_social + cuit de emisores_arca. Fallback: vacío."""
    try:
        from database import get_db
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT razon_social, cuit FROM emisores_arca WHERE nombre = %s", (nombre,)
            ).fetchone()
        finally:
            conn.close()
        if row:
            return {"razon_social": row["razon_social"] or "", "cuit": row["cuit"] or ""}
    except Exception:
        pass
    return {"razon_social": "", "cuit": ""}


# ---------------------------------------------------------------------------
# Fuentes (TT Commons + JetBrains Mono, vendoreadas — mismas que usa la web)
# y logo ARCA (SVG inline, `fill=currentColor` para teñir por contexto).
# Playwright renderiza con base `about:blank`: todo va embebido, nada de
# `<img src="archivo-relativo">`.
# ---------------------------------------------------------------------------

_FONTS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "frontend", "public", "fonts", "woff2"
)
_FONT_FILES = [
    ("tt-commons-400.woff2", "TT Commons", 400),
    ("tt-commons-500.woff2", "TT Commons", 500),
    ("tt-commons-600.woff2", "TT Commons", 600),
    ("tt-commons-700.woff2", "TT Commons", 700),
    ("tt-commons-800.woff2", "TT Commons", 800),
    ("jetbrains-mono-400.woff2", "JetBrains Mono", 400),
    ("jetbrains-mono-500.woff2", "JetBrains Mono", 500),
]

_ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")


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


@lru_cache(maxsize=1)
def _arca_logo_svg() -> str:
    try:
        with open(os.path.join(_ASSETS_DIR, "arca-logo.svg"), encoding="utf-8") as fh:
            svg = fh.read()
    except OSError:
        return ""
    # Descartar el prolog XML (ruido dentro de un doc HTML) y teñir por CSS.
    svg = svg.split("?>", 1)[-1].strip() if svg.lstrip().startswith("<?xml") else svg
    if "<svg " in svg and "fill=" not in svg.split(">", 1)[0]:
        svg = svg.replace("<svg ", '<svg fill="currentColor" ', 1)
    return svg


def _arca_logo(width: int) -> str:
    svg = _arca_logo_svg()
    if not svg:
        return ""
    return svg.replace(
        "<svg ", f'<svg style="width:{width}px;height:auto;display:block" ', 1
    )


# ---------------------------------------------------------------------------
# Contexto único (mismo dato para las 3 piezas)
# ---------------------------------------------------------------------------


def factura_filename(factura, *, layout: str = "clasica") -> str:
    """Nombre de archivo canónico del PDF de una factura/NC (admin + portal cliente)."""
    letra = _CBTE_TIPO_LABEL.get(factura.cbte_tipo, "X")
    prefijo = "NC" if _CBTE_TIPO_NOTA.get(factura.cbte_tipo, False) else "Factura"
    sufijo = "" if layout == "clasica" else f"-{layout}"
    return f"{prefijo}-{letra}-{factura.pto_vta:05d}-{factura.cbte_nro or 0:08d}{sufijo}.pdf"


def _conceptos(pedido: dict, factura) -> list[dict]:
    """Ítems del comprobante ← `pedido.items`. Si no hay líneas (pedidos
    viejos o ítems personalizados sin persistir), cae a una sola línea con
    el neto total de la factura — nunca inventa un desglose que no existe."""
    items = pedido.get("items") or []
    if not items:
        desc = (
            pedido.get("descripcion")
            or f"Alquiler de equipos — Pedido #{pedido.get('numero_pedido') or pedido.get('id', '')}"
        )
        return [{
            "codigo": "001", "desc": desc, "detalle": "",
            "cant": "1,00", "uMedida": "unidad", "bonif": "0,00",
            "precioUnitFmt": _plain(factura.imp_neto), "subtotalFmt": _plain(factura.imp_neto),
            "importeStr": _money(factura.imp_neto),
        }]

    jornadas = pedido.get("cantidad_jornadas") or 1
    out = []
    for i, it in enumerate(items):
        cobro_fijo = (it.get("cobro_modo") or "jornada") == "fijo"
        detalle = "Cargo único" if cobro_fijo else f"{jornadas} jornada{'s' if jornadas != 1 else ''}"
        subtotal = it.get("subtotal") or 0
        cantidad = it.get("cantidad") or 1
        out.append({
            "codigo": f"{i + 1:03d}",
            "desc": it.get("nombre") or it.get("nombre_libre") or "Ítem",
            "detalle": detalle,
            "cant": _plain(cantidad),
            "uMedida": "unidad",
            "bonif": "0,00",
            "precioUnitFmt": _plain(it.get("precio_jornada") or 0),
            "subtotalFmt": _plain(subtotal),
            "importeStr": _money(subtotal),
        })
    return out


def _build_ctx(factura, pedido: dict) -> dict:
    em_key = factura.emisor if factura.emisor in _EMISORES_DATA else "santini"
    em_data = _EMISORES_DATA[em_key]
    em_row = _emisor_row(factura.emisor)

    letra = _CBTE_TIPO_LABEL.get(factura.cbte_tipo, "C")
    es_nc = _CBTE_TIPO_NOTA.get(factura.cbte_tipo, False)
    cod = f"{factura.cbte_tipo:02d}"

    doc_label = _DOC_TIPO_LABEL.get(factura.doc_tipo, "Documento")
    doc_nro = factura.cliente_cuit or factura.doc_nro or "—"
    # CUIT/CUIL con guiones si vienen en crudo (11 dígitos).
    if doc_nro and doc_nro.isdigit() and len(doc_nro) == 11:
        doc_nro = f"{doc_nro[:2]}-{doc_nro[2:10]}-{doc_nro[10:]}"

    total_pedido = pedido.get("monto_total")
    pagado = pedido.get("monto_pagado") or 0
    venta = "Contado" if total_pedido is None or pagado >= total_pedido else "Cuenta corriente"

    fecha_desde = _fdate(pedido.get("fecha_desde"))
    fecha_hasta = _fdate(pedido.get("fecha_hasta"))
    # No hay campo de vencimiento comercial propio en el pedido: por default
    # de negocio (alquiler se abona antes/al inicio) se usa la fecha de inicio.
    vto_pago = fecha_desde

    mostrar_iva = letra in ("A", "B") and factura.imp_iva > 0

    qr_url = ""
    if factura.qr_payload:
        qr_url = factura.qr_payload

    return {
        "letra": letra, "cod": cod, "es_nc": es_nc,
        "titulo": ("NOTA DE CRÉDITO " if es_nc else "FACTURA ") + letra,
        "emisor": {
            "razonSocial": em_row["razon_social"] or "—",
            "cuit": em_row["cuit"] or "—",
            "cond": em_data["cond_iva_label"],
            "dom": em_data["domicilio"],
            "iibb": em_data["iibb"],
            "inicio": em_data["inicio_actividades"],
            "ptoVta": f"{factura.pto_vta:05d}",
        },
        "comp": {
            "nro": f"{factura.cbte_nro or 0:08d}",
            "fecha": _fdate(factura.fecha_emision),
        },
        "periodo": {"desde": fecha_desde, "hasta": fecha_hasta, "vto": vto_pago},
        "receptor": {
            "nombre": factura.razon_social or pedido.get("cliente_nombre") or "—",
            "docLabel": doc_label,
            "docNro": doc_nro,
            "cond": _COND_IVA_LABEL.get(factura.condicion_iva_receptor, "—"),
            "dom": pedido.get("cliente_domicilio_fiscal") or "—",
            "venta": venta,
        },
        "conceptos": _conceptos(pedido, factura),
        "tot": {
            "discrimina": mostrar_iva,
            "netoStr": _money(factura.imp_neto), "ivaStr": _money(factura.imp_iva),
            "subStr": _money(factura.imp_neto), "otrosStr": _money(0),
            "totalStr": _money(factura.imp_total), "ivaPct": "21%",
        },
        "cae": {"nro": factura.cae or "—", "vto": _fdate(factura.cae_vto)},
        "qr": {"url": qr_url, "has": bool(qr_url), "pending": not qr_url},
    }


def _qr_img(url: str, size: int) -> str:
    try:
        from arca_fe.qr import _build_qr_image_data_uri
        return (
            f'<img src="{_build_qr_image_data_uri(url)}" width="{size}" height="{size}" '
            f'alt="QR AFIP" style="display:block">'
        )
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# 1a — Clásica A4 (réplica fiel del comprobante oficial AFIP/ARCA)
# ---------------------------------------------------------------------------


def _factura_clasica_html(f: dict) -> str:
    qr_block = _qr_img(f["qr"]["url"], 112) if f["qr"]["has"] else ""
    if not qr_block:
        # Sin payload O la generación falló (nunca dejar un hueco en blanco).
        qr_block = (
            '<div style="width:112px;height:112px;border:1px solid #000;display:flex;'
            'align-items:center;justify-content:center;font-size:9px;color:#666;">QR</div>'
        )

    iibb_line = (
        f'<div style="margin-bottom:4px;"><span style="font-weight:700;">Ingresos Brutos:</span> {_e(f["emisor"]["iibb"])}</div>'
        if f["emisor"]["iibb"] else ""
    )
    inicio_line = (
        f'<div><span style="font-weight:700;">Fecha de Inicio de Actividades:</span> {_e(f["emisor"]["inicio"])}</div>'
        if f["emisor"]["inicio"] else ""
    )

    filas_items = "".join(f"""
      <div style="display:grid;grid-template-columns:52px 1fr 62px 74px 96px 58px 100px;font-size:10px;">
        <div style="padding:7px 6px;border-right:1px solid #000;">{_e(c['codigo'])}</div>
        <div style="padding:7px 6px;border-right:1px solid #000;">
          <div style="font-weight:700;">{_e(c['desc'])}</div>
          <div style="color:#333;font-size:9px;margin-top:2px;">{_e(c['detalle'])}</div>
        </div>
        <div style="padding:7px 6px;border-right:1px solid #000;text-align:right;font-variant-numeric:tabular-nums;">{_e(c['cant'])}</div>
        <div style="padding:7px 6px;border-right:1px solid #000;">{_e(c['uMedida'])}</div>
        <div style="padding:7px 6px;border-right:1px solid #000;text-align:right;font-variant-numeric:tabular-nums;">{_e(c['precioUnitFmt'])}</div>
        <div style="padding:7px 6px;border-right:1px solid #000;text-align:right;font-variant-numeric:tabular-nums;">{_e(c['bonif'])}</div>
        <div style="padding:7px 6px;text-align:right;font-variant-numeric:tabular-nums;">{_e(c['subtotalFmt'])}</div>
      </div>""" for c in f["conceptos"])

    if f["tot"]["discrimina"]:
        totales_iva = f"""
            <div style="display:flex;justify-content:space-between;padding:3px 0;"><span style="font-weight:700;">Importe Neto Gravado: $</span><span style="font-variant-numeric:tabular-nums;">{f['tot']['netoStr'][2:]}</span></div>
            <div style="display:flex;justify-content:space-between;padding:3px 0;"><span style="font-weight:700;">IVA {f['tot']['ivaPct']}: $</span><span style="font-variant-numeric:tabular-nums;">{f['tot']['ivaStr'][2:]}</span></div>"""
    else:
        totales_iva = f"""
            <div style="display:flex;justify-content:space-between;padding:3px 0;"><span style="font-weight:700;">Subtotal: $</span><span style="font-variant-numeric:tabular-nums;">{f['tot']['subStr'][2:]}</span></div>"""

    body = f"""
        <div style="position:absolute;top:10px;right:14px;font-size:9px;letter-spacing:0.05em;z-index:3;">ORIGINAL</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;position:relative;border-bottom:1px solid #000;">
          <div style="position:absolute;left:50%;top:0;transform:translate(-50%,-1px);width:58px;height:60px;background:#fff;border:1px solid #000;display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:2;">
            <span style="font-size:34px;font-weight:700;line-height:1;">{_e(f['letra'])}</span>
            <span style="font-size:7.5px;margin-top:2px;">COD. {_e(f['cod'])}</span>
          </div>
          <div style="padding:20px 22px 22px;border-right:1px solid #000;min-height:158px;">
            <div style="font-size:18px;font-weight:700;margin-bottom:12px;">{_e(f['emisor']['razonSocial'])}</div>
            <div style="margin-bottom:4px;"><span style="font-weight:700;">Razón Social:</span> {_e(f['emisor']['razonSocial'])}</div>
            <div style="margin-bottom:4px;"><span style="font-weight:700;">Domicilio Comercial:</span> {_e(f['emisor']['dom'])}</div>
            <div><span style="font-weight:700;">Condición frente al IVA:</span> {_e(f['emisor']['cond'])}</div>
          </div>
          <div style="padding:20px 22px 22px 40px;">
            <div style="font-size:26px;font-weight:700;margin-bottom:2px;">{_e(f['titulo'])}</div>
            <div style="font-size:10px;margin-bottom:12px;">Cód. {_e(f['cod'])}</div>
            <div style="margin-bottom:4px;"><span style="font-weight:700;">Punto de Venta: </span>{_e(f['emisor']['ptoVta'])}<span style="font-weight:700;margin-left:16px;">Comp. Nro: </span>{_e(f['comp']['nro'])}</div>
            <div style="margin-bottom:4px;"><span style="font-weight:700;">Fecha de Emisión:</span> {_e(f['comp']['fecha'])}</div>
            <div style="margin-bottom:4px;"><span style="font-weight:700;">CUIT:</span> {_e(f['emisor']['cuit'])}</div>
            {iibb_line}
            {inicio_line}
          </div>
        </div>

        <div style="padding:7px 22px;border-bottom:1px solid #000;display:flex;gap:28px;">
          <span><span style="font-weight:700;">Período Facturado Desde:</span> {_e(f['periodo']['desde'])}</span>
          <span><span style="font-weight:700;">Hasta:</span> {_e(f['periodo']['hasta'])}</span>
          <span><span style="font-weight:700;">Fecha de Vto. para el pago:</span> {_e(f['periodo']['vto'])}</span>
        </div>

        <div style="padding:12px 22px;border-bottom:1px solid #000;">
          <div style="display:flex;gap:28px;margin-bottom:4px;">
            <span><span style="font-weight:700;">{_e(f['receptor']['docLabel'])}:</span> {_e(f['receptor']['docNro'])}</span>
            <span><span style="font-weight:700;">Condición frente al IVA:</span> {_e(f['receptor']['cond'])}</span>
          </div>
          <div style="margin-bottom:4px;"><span style="font-weight:700;">Apellido y Nombre / Razón Social:</span> {_e(f['receptor']['nombre'])}</div>
          <div style="display:flex;gap:28px;">
            <span><span style="font-weight:700;">Domicilio:</span> {_e(f['receptor']['dom'])}</span>
            <span><span style="font-weight:700;">Condición de venta:</span> {_e(f['receptor']['venta'])}</span>
          </div>
        </div>

        <div style="padding:14px 22px 0;">
          <div style="display:grid;grid-template-columns:52px 1fr 62px 74px 96px 58px 100px;background:#e6e6e6;border:1px solid #000;font-weight:700;font-size:9.5px;">
            <div style="padding:5px 6px;border-right:1px solid #000;">Código</div>
            <div style="padding:5px 6px;border-right:1px solid #000;">Producto / Servicio</div>
            <div style="padding:5px 6px;border-right:1px solid #000;text-align:right;">Cantidad</div>
            <div style="padding:5px 6px;border-right:1px solid #000;">U. Medida</div>
            <div style="padding:5px 6px;border-right:1px solid #000;text-align:right;">Precio Unit.</div>
            <div style="padding:5px 6px;border-right:1px solid #000;text-align:right;">% Bonif.</div>
            <div style="padding:5px 6px;text-align:right;">Subtotal</div>
          </div>
          <div style="border-left:1px solid #000;border-right:1px solid #000;border-bottom:1px solid #000;">{filas_items}
          </div>
        </div>

        <div style="flex:1;"></div>

        <div style="padding:0 22px 6px;display:flex;justify-content:flex-end;">
          <div style="width:300px;font-size:11px;">{totales_iva}
            <div style="display:flex;justify-content:space-between;padding:3px 0;"><span style="font-weight:700;">Importe Otros Tributos: $</span><span style="font-variant-numeric:tabular-nums;">{f['tot']['otrosStr'][2:]}</span></div>
            <div style="display:flex;justify-content:space-between;padding:10px 12px;margin-top:6px;background:#000;color:#fff;font-weight:700;font-size:14px;"><span>Importe Total: $</span><span style="font-variant-numeric:tabular-nums;">{f['tot']['totalStr'][2:]}</span></div>
          </div>
        </div>

        <div style="border-top:1px solid #000;padding:14px 22px 18px;display:grid;grid-template-columns:120px 1fr;gap:18px;align-items:center;">
          <div>{qr_block}</div>
          <div style="align-self:flex-end;text-align:right;">
            <div style="margin-bottom:9px;">{_arca_logo(120)}</div>
            <div style="display:flex;justify-content:flex-end;gap:8px;margin-bottom:2px;"><span style="font-weight:700;">CAE N°:</span><span style="font-variant-numeric:tabular-nums;">{_e(f['cae']['nro'])}</span></div>
            <div style="display:flex;justify-content:flex-end;gap:8px;"><span style="font-weight:700;">Fecha de Vto. de CAE:</span><span style="font-variant-numeric:tabular-nums;">{_e(f['cae']['vto'])}</span></div>
            <div style="margin-top:10px;font-size:9px;color:#333;">Comprobante Autorizado — Verifique la validez de este comprobante en www.arca.gob.ar</div>
            <div style="margin-top:4px;font-size:9px;color:#333;">Pág. 1/1</div>
          </div>
        </div>
"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width">
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  html,body {{ background:#fff; }}
  body {{ width:794px; min-height:1123px; background:#fff; color:#000;
          font-family:Arial,Helvetica,sans-serif; font-size:10.5px; line-height:1.35;
          border:1px solid #000; position:relative; display:flex; flex-direction:column; }}
</style>
</head>
<body>{body}
</body>
</html>"""


# ---------------------------------------------------------------------------
# 1b — Celular (comprobante vertical compacto, para compartir por WhatsApp)
# ---------------------------------------------------------------------------


def _factura_mobile_html(f: dict) -> str:
    tipo_banner = "Nota de crédito electrónica · Original" if f["es_nc"] else "Factura electrónica · Original"

    qr_block = _qr_img(f["qr"]["url"], 120) if f["qr"]["has"] else ""
    if not qr_block:
        qr_block = (
            '<div style="width:120px;height:120px;display:flex;align-items:center;justify-content:center;'
            'font-family:\'JetBrains Mono\',monospace;font-size:10px;color:#8a97a3;">QR…</div>'
        )

    conceptos_html = "".join(f"""
        <div style="display:flex;justify-content:space-between;gap:12px;padding:7px 0;border-top:1px solid #f2f5f7;">
          <div style="min-width:0;">
            <div style="font-size:14px;font-weight:600;">{_e(c['desc'])}</div>
            <div style="font-size:12px;color:#8a97a3;margin-top:1px;">{_e(c['detalle'])}</div>
          </div>
          <div style="font-size:14px;font-weight:600;font-variant-numeric:tabular-nums;white-space:nowrap;">{_e(c['importeStr'])}</div>
        </div>""" for c in f["conceptos"])

    if f["tot"]["discrimina"]:
        totales_iva = f"""
        <div style="display:flex;justify-content:space-between;font-size:14px;color:#5b6875;padding:2.5px 0;"><span>Neto gravado</span><span style="font-variant-numeric:tabular-nums;letter-spacing:0.04em;">{_e(f['tot']['netoStr'])}</span></div>
        <div style="display:flex;justify-content:space-between;font-size:14px;color:#5b6875;padding:2.5px 0;"><span>IVA {_e(f['tot']['ivaPct'])}</span><span style="font-variant-numeric:tabular-nums;letter-spacing:0.04em;">{_e(f['tot']['ivaStr'])}</span></div>
        <div style="height:1px;background:#eef1f4;margin:10px 0;"></div>"""
    else:
        totales_iva = ""

    body = f"""
    <div style="padding:18px 20px;display:flex;align-items:center;justify-content:space-between;gap:12px;">
      <div style="min-width:0;display:flex;align-items:center;">
        <div style="width:132px;color:#16202b;">{_arca_logo(132)}</div>
      </div>
      <div style="flex:none;display:flex;flex-direction:column;align-items:center;justify-content:center;width:54px;height:60px;border:1.5px solid #16202b;border-radius:10px;">
        <span style="font-size:31px;font-weight:800;line-height:1;">{_e(f['letra'])}</span>
        <span style="font-family:'JetBrains Mono',monospace;font-size:8px;letter-spacing:0.08em;margin-top:2px;">COD {_e(f['cod'])}</span>
      </div>
    </div>

    <div style="background:#f7f8fa;color:#98a3ae;text-align:center;font-family:'JetBrains Mono',monospace;font-weight:500;font-size:10px;letter-spacing:0.18em;text-transform:uppercase;padding:8px;border-top:1px solid #eef1f4;border-bottom:1px solid #eef1f4;">{_e(tipo_banner)}</div>

    <div style="padding:11px 20px;border-bottom:1px solid #eef1f4;display:grid;grid-template-columns:1fr 1fr 1fr;gap:9px 14px;">
      <div><div style="font-family:'JetBrains Mono',monospace;font-size:8.5px;letter-spacing:0.06em;text-transform:uppercase;color:#98a3ae;line-height:1;">Punto de venta</div><div style="font-size:13.5px;font-weight:600;line-height:1.25;font-variant-numeric:tabular-nums;">{_e(f['emisor']['ptoVta'])}</div></div>
      <div><div style="font-family:'JetBrains Mono',monospace;font-size:8.5px;letter-spacing:0.06em;text-transform:uppercase;color:#98a3ae;line-height:1;">Comp. Nro</div><div style="font-size:13.5px;font-weight:600;line-height:1.25;font-variant-numeric:tabular-nums;">{_e(f['comp']['nro'])}</div></div>
      <div><div style="font-family:'JetBrains Mono',monospace;font-size:8.5px;letter-spacing:0.06em;text-transform:uppercase;color:#98a3ae;line-height:1;">Fecha de emisión</div><div style="font-size:13.5px;font-weight:600;line-height:1.25;font-variant-numeric:tabular-nums;">{_e(f['comp']['fecha'])}</div></div>
      <div style="grid-column:span 2;"><div style="font-family:'JetBrains Mono',monospace;font-size:8.5px;letter-spacing:0.06em;text-transform:uppercase;color:#98a3ae;line-height:1;">Período facturado</div><div style="font-size:13.5px;font-weight:600;line-height:1.25;font-variant-numeric:tabular-nums;">{_e(f['periodo']['desde'])} → {_e(f['periodo']['hasta'])}</div></div>
      <div><div style="font-family:'JetBrains Mono',monospace;font-size:8.5px;letter-spacing:0.06em;text-transform:uppercase;color:#98a3ae;line-height:1;">Vto. de pago</div><div style="font-size:13.5px;font-weight:600;line-height:1.25;font-variant-numeric:tabular-nums;">{_e(f['periodo']['vto'])}</div></div>
    </div>

    <div style="padding:14px 20px;border-bottom:1px solid #eef1f4;display:flex;flex-direction:column;gap:12px;">
      <div style="display:flex;gap:8px;">
        <div style="flex:none;width:42px;height:19px;display:flex;align-items:center;gap:5px;">
          <span style="width:6px;height:6px;border-radius:999px;background:#1c5fb8;flex:none;"></span>
          <span style="font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:0.12em;text-transform:uppercase;color:#98a3ae;">De</span>
        </div>
        <div style="flex:1;min-width:0;">
          <div style="font-size:16px;font-weight:700;line-height:1.19;">{_e(f['emisor']['razonSocial'])}</div>
          <div style="font-size:12.5px;color:#5b6875;margin-top:3px;font-variant-numeric:tabular-nums;">CUIT <span style="font-weight:600;color:#16202b;">{_e(f['emisor']['cuit'])}</span> · {_e(f['emisor']['cond'])}</div>
          <div style="font-size:12.5px;color:#5b6875;">{_e(f['emisor']['dom'])}</div>
        </div>
      </div>
      <div style="display:flex;gap:8px;">
        <div style="flex:none;width:42px;height:19px;display:flex;align-items:center;gap:5px;">
          <span style="width:6px;height:6px;border-radius:999px;background:#16202b;flex:none;"></span>
          <span style="font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:0.12em;text-transform:uppercase;color:#98a3ae;">Para</span>
        </div>
        <div style="flex:1;min-width:0;">
          <div style="font-size:16px;font-weight:700;line-height:1.19;">{_e(f['receptor']['nombre'])}</div>
          <div style="font-size:12.5px;color:#5b6875;margin-top:3px;font-variant-numeric:tabular-nums;">{_e(f['receptor']['docLabel'])} <span style="font-weight:600;color:#16202b;">{_e(f['receptor']['docNro'])}</span> · {_e(f['receptor']['cond'])}</div>
          <div style="font-size:12.5px;color:#5b6875;">{_e(f['receptor']['dom'])}</div>
        </div>
      </div>
    </div>

    <div style="padding:14px 20px;border-bottom:1px solid #eef1f4;">
      <div style="font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:0.14em;text-transform:uppercase;color:#8a97a3;margin-bottom:6px;">Conceptos</div>{conceptos_html}
    </div>

    <div style="padding:14px 20px 16px;border-bottom:1px solid #eef1f4;">{totales_iva}
      <div style="display:flex;justify-content:space-between;align-items:baseline;">
        <span style="font-size:15px;font-weight:700;">Total</span>
        <span style="font-size:26px;font-weight:800;letter-spacing:-0.02em;font-variant-numeric:tabular-nums;">{_e(f['tot']['totalStr'])}</span>
      </div>
    </div>

    <div style="padding:14px 20px 18px;background:#f5f7f9;display:flex;gap:14px;align-items:center;">
      <div style="flex:none;background:#fff;border:1px solid #e6e9ec;border-radius:10px;padding:7px;">{qr_block}</div>
      <div style="flex:1;min-width:0;font-size:12.5px;color:#5b6875;line-height:1.4;">
        <div style="font-weight:600;color:#16202b;margin-bottom:3px;">Comprobante autorizado</div>
        <div>CAE N° <span style="color:#16202b;font-weight:600;font-variant-numeric:tabular-nums;">{_e(f['cae']['nro'])}</span></div>
        <div>Vto. CAE <span style="color:#16202b;font-weight:600;font-variant-numeric:tabular-nums;">{_e(f['cae']['vto'])}</span></div>
        <div style="margin-top:5px;">Escaneá el QR para validar en arca.gob.ar</div>
      </div>
    </div>
"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width">
{_fonts_css()}
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  html,body {{ background:#fff; }}
  body {{ width:392px; background:#fff; font-family:'TT Commons',ui-sans-serif,sans-serif;
          color:#16202b; overflow:hidden; }}
</style>
</head>
<body>{body}
</body>
</html>"""


# ---------------------------------------------------------------------------
# 1c — A4 formal (identidad de la mobile, alternativa a la clásica)
# ---------------------------------------------------------------------------


def _factura_formal_html(f: dict) -> str:
    tipo_banner = "Nota de crédito electrónica · Original" if f["es_nc"] else "Factura electrónica · Original"

    qr_block = _qr_img(f["qr"]["url"], 150) if f["qr"]["has"] else ""
    if not qr_block:
        qr_block = (
            '<div style="width:150px;height:150px;display:flex;align-items:center;justify-content:center;'
            'font-family:\'JetBrains Mono\',monospace;font-size:11px;color:#8a97a3;">QR…</div>'
        )

    iibb_line = (
        f'<div><span style="font-weight:600;color:#16202b;">Ingresos Brutos:</span> {_e(f["emisor"]["iibb"])}</div>'
        if f["emisor"]["iibb"] else ""
    )
    inicio_line = (
        f'<div><span style="font-weight:600;color:#16202b;">Inicio de Actividades:</span> {_e(f["emisor"]["inicio"])}</div>'
        if f["emisor"]["inicio"] else ""
    )

    filas_items = "".join(f"""
      <div style="display:grid;grid-template-columns:1fr 90px 150px 150px;gap:0;padding:12px 0;border-bottom:1px solid #eef1f4;align-items:baseline;">
        <div><div style="font-size:15px;font-weight:600;">{_e(c['desc'])}</div><div style="font-size:12.5px;color:#8a97a3;margin-top:2px;">{_e(c['detalle'])}</div></div>
        <div style="text-align:right;font-size:14px;font-variant-numeric:tabular-nums;">{_e(c['cant'])}</div>
        <div style="text-align:right;font-size:14px;font-variant-numeric:tabular-nums;">{_e(c['precioUnitFmt'])}</div>
        <div style="text-align:right;font-size:14px;font-weight:600;font-variant-numeric:tabular-nums;">{_e(c['subtotalFmt'])}</div>
      </div>""" for c in f["conceptos"])

    if f["tot"]["discrimina"]:
        totales_iva = f"""
              <div style="display:flex;justify-content:space-between;font-size:14px;color:#5b6875;padding:4px 0;"><span>Neto gravado</span><span style="font-variant-numeric:tabular-nums;">{_e(f['tot']['netoStr'])}</span></div>
              <div style="display:flex;justify-content:space-between;font-size:14px;color:#5b6875;padding:4px 0;"><span>IVA {_e(f['tot']['ivaPct'])}</span><span style="font-variant-numeric:tabular-nums;">{_e(f['tot']['ivaStr'])}</span></div>"""
    else:
        totales_iva = ""

    body = f"""
        <div style="padding:38px 44px 24px;display:flex;justify-content:space-between;align-items:center;">
          {_arca_logo(212)}
          <div style="flex:none;display:flex;flex-direction:column;align-items:center;justify-content:center;width:78px;height:88px;border:2px solid #16202b;border-radius:12px;">
            <span style="font-size:46px;font-weight:800;line-height:1;">{_e(f['letra'])}</span>
            <span style="font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:0.08em;margin-top:3px;">COD {_e(f['cod'])}</span>
          </div>
        </div>

        <div style="background:#f7f8fa;color:#98a3ae;text-align:center;font-family:'JetBrains Mono',monospace;font-weight:500;font-size:12px;letter-spacing:0.2em;text-transform:uppercase;padding:11px;border-top:1px solid #eef1f4;border-bottom:1px solid #eef1f4;">{_e(tipo_banner)}</div>

        <div style="padding:30px 44px;display:grid;grid-template-columns:1fr 1fr;gap:36px;border-bottom:1px solid #eef1f4;">
          <div>
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;"><span style="width:7px;height:7px;border-radius:999px;background:#1c5fb8;flex:none;"></span><span style="font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:0.16em;text-transform:uppercase;color:#98a3ae;">Emisor</span></div>
            <div style="font-size:21px;font-weight:700;line-height:1.15;margin-bottom:10px;">{_e(f['emisor']['razonSocial'])}</div>
            <div style="font-size:14px;line-height:1.55;color:#5b6875;font-variant-numeric:tabular-nums;">
              <div><span style="font-weight:600;color:#16202b;">CUIT:</span> {_e(f['emisor']['cuit'])}</div>
              <div><span style="font-weight:600;color:#16202b;">Condición frente al IVA:</span> {_e(f['emisor']['cond'])}</div>
              <div><span style="font-weight:600;color:#16202b;">Domicilio Comercial:</span> {_e(f['emisor']['dom'])}</div>
              {iibb_line}
              {inicio_line}
            </div>
          </div>
          <div>
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;"><span style="width:7px;height:7px;border-radius:999px;background:#16202b;flex:none;"></span><span style="font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:0.16em;text-transform:uppercase;color:#98a3ae;">Receptor</span></div>
            <div style="font-size:21px;font-weight:700;line-height:1.15;margin-bottom:10px;">{_e(f['receptor']['nombre'])}</div>
            <div style="font-size:14px;line-height:1.55;color:#5b6875;font-variant-numeric:tabular-nums;">
              <div><span style="font-weight:600;color:#16202b;">{_e(f['receptor']['docLabel'])}:</span> {_e(f['receptor']['docNro'])}</div>
              <div><span style="font-weight:600;color:#16202b;">Condición frente al IVA:</span> {_e(f['receptor']['cond'])}</div>
              <div><span style="font-weight:600;color:#16202b;">Domicilio:</span> {_e(f['receptor']['dom'])}</div>
              <div><span style="font-weight:600;color:#16202b;">Condición de venta:</span> {_e(f['receptor']['venta'])}</div>
            </div>
          </div>
        </div>

        <div style="padding:22px 44px;display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px 20px;border-bottom:1px solid #eef1f4;">
          <div><div style="font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:0.1em;text-transform:uppercase;color:#98a3ae;">Punto de venta</div><div style="font-size:16px;font-weight:600;margin-top:2px;font-variant-numeric:tabular-nums;">{_e(f['emisor']['ptoVta'])}</div></div>
          <div><div style="font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:0.1em;text-transform:uppercase;color:#98a3ae;">Comp. Nro</div><div style="font-size:16px;font-weight:600;margin-top:2px;font-variant-numeric:tabular-nums;">{_e(f['comp']['nro'])}</div></div>
          <div><div style="font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:0.1em;text-transform:uppercase;color:#98a3ae;">Fecha de emisión</div><div style="font-size:16px;font-weight:600;margin-top:2px;font-variant-numeric:tabular-nums;">{_e(f['comp']['fecha'])}</div></div>
          <div style="grid-column:span 2;"><div style="font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:0.1em;text-transform:uppercase;color:#98a3ae;">Período facturado</div><div style="font-size:16px;font-weight:600;margin-top:2px;font-variant-numeric:tabular-nums;">{_e(f['periodo']['desde'])} → {_e(f['periodo']['hasta'])}</div></div>
          <div><div style="font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:0.1em;text-transform:uppercase;color:#98a3ae;">Vto. de pago</div><div style="font-size:16px;font-weight:600;margin-top:2px;font-variant-numeric:tabular-nums;">{_e(f['periodo']['vto'])}</div></div>
        </div>

        <div style="padding:24px 44px 0;">
          <div style="display:grid;grid-template-columns:1fr 90px 150px 150px;gap:0;font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:0.1em;text-transform:uppercase;color:#98a3ae;padding-bottom:8px;border-bottom:1.5px solid #16202b;">
            <div>Descripción</div>
            <div style="text-align:right;">Cantidad</div>
            <div style="text-align:right;">P. Unitario</div>
            <div style="text-align:right;">Subtotal</div>
          </div>{filas_items}

          <div style="display:flex;justify-content:flex-end;margin-top:20px;">
            <div style="width:300px;">{totales_iva}
              <div style="display:flex;justify-content:space-between;align-items:baseline;margin-top:8px;padding-top:12px;border-top:1.5px solid #16202b;"><span style="font-size:17px;font-weight:700;">Total</span><span style="font-size:26px;font-weight:800;font-variant-numeric:tabular-nums;">{_e(f['tot']['totalStr'])}</span></div>
            </div>
          </div>
        </div>

        <div style="flex:1;"></div>

        <div style="padding:22px 44px 34px;border-top:1px solid #eef1f4;display:flex;gap:22px;align-items:center;">
          <div style="flex:none;background:#fff;border:1px solid #e6e9ec;border-radius:12px;padding:9px;">{qr_block}</div>
          <div style="flex:1;">
            <div style="font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:0.14em;text-transform:uppercase;color:#98a3ae;margin-bottom:6px;">Comprobante autorizado por ARCA</div>
            <div style="font-size:15px;margin-bottom:3px;"><span style="color:#5b6875;">CAE N° </span><span style="font-weight:600;font-variant-numeric:tabular-nums;">{_e(f['cae']['nro'])}</span></div>
            <div style="font-size:15px;margin-bottom:12px;"><span style="color:#5b6875;">Vto. CAE </span><span style="font-weight:600;font-variant-numeric:tabular-nums;">{_e(f['cae']['vto'])}</span></div>
            <div style="font-size:13px;color:#8a97a3;line-height:1.45;">Verificá la validez de este comprobante escaneando el QR o en www.arca.gob.ar</div>
          </div>
        </div>
"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width">
{_fonts_css()}
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  html,body {{ background:#fff; }}
  body {{ width:794px; min-height:1123px; background:#fff; font-family:'TT Commons',ui-sans-serif,sans-serif;
          color:#16202b; display:flex; flex-direction:column; }}
</style>
</head>
<body>{body}
</body>
</html>"""


# ---------------------------------------------------------------------------
# Punto de entrada único — dispatch por layout
# ---------------------------------------------------------------------------

_LAYOUTS = {
    "clasica": _factura_clasica_html,
    "celular": _factura_mobile_html,
    "formal": _factura_formal_html,
}

# Ancho fijo del comprobante "celular" (mismo valor que el `width` del body
# en `_factura_mobile_html`). Alto = None → `pdf._render_pdf` mide el alto
# real del contenido (el comprobante no es A4, es una tarjeta angosta que
# tiene que terminar donde termina el contenido, no a media hoja).
MOBILE_PAGE_WIDTH = 392


def page_size_for_layout(layout: str) -> tuple[int, int | None] | None:
    """Tamaño de página para `pdf._render_pdf(html, page_size=...)`.
    None → A4 (default, clásica/formal). Un tuple → tamaño propio (celular)."""
    return (MOBILE_PAGE_WIDTH, None) if layout == "celular" else None


def factura_html(factura, pedido: dict, layout: str = "clasica") -> str:
    """Genera el HTML completo de la factura (Factura A/B/C o Nota de Crédito).

    `factura` es una instancia de `services.facturacion.repo.Factura`.
    `pedido` viene de `services.facturacion.engine._get_pedido` (items + cliente
    enriquecidos). `layout`: 'clasica' (default, réplica oficial AFIP/ARCA) ·
    'celular' (compacta, para compartir por WhatsApp) · 'formal' (A4, identidad
    de la celular).
    """
    builder = _LAYOUTS.get(layout, _factura_clasica_html)
    ctx = _build_ctx(factura, pedido)
    return builder(ctx)
