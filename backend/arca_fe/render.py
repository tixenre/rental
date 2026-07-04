"""arca_fe.render — arma el HTML de comprobantes fiscales (Factura A/B/C, Nota de Crédito).
PORTABLE. (Se llama `render`, no `pdf`: este módulo nunca generó bytes de PDF — solo HTML; el
nombre viejo databa de cuando la librería sí lo hacía. Convertir a PDF es responsabilidad del
consumidor, ver más abajo.)

Tres layouts, un mismo contexto interno (`_build_ctx`) — cada uno con su `LayoutInfo` (`id`,
`nombre`, `descripcion`, `advertencia`) en `LAYOUTS_INFO`, para que el consumidor arme un selector
real con esas mismas descripciones en vez de inventar copy propio:

- **`oficial`**: réplica fiel del comprobante oficial AFIP/ARCA, A4 imprimible. Detalle completo
  por ítem (cantidad, unidad de medida, precio unitario, bonificación).
- **`detallada`**: A4 con identidad visual moderna, mismo nivel de detalle que `oficial` — una
  alternativa prolija, no un resumen.
- **`simplificada`**: comprobante vertical compacto 4:5, pensado para compartir (WhatsApp/redes) —
  el default. **No es "la versión para celular" de las otras dos** — es un tipo de comprobante
  distinto: cada ítem se resume a descripción + importe, SIN cantidad/precio unitario/bonificación.
  **Esto se hace cumplir en código, no es solo una advertencia**: si algún ítem necesita mostrar
  cantidad != 1, bonificación, unidad de medida no estándar o detalle adicional,
  `renderizar_comprobante_html` levanta `ValueError` en vez de generar un comprobante que esconde
  esa información — para esos casos usar `oficial` o `detallada` (`_validar_apto_para_simplificada`).

Los tres son agnósticos de marca: usan el logo oficial de ARCA (la agencia, no el emisor) y
muestran todo lo que AFIP exige (CAE, QR fiscal RG4892, discriminación de IVA, leyenda de
Transparencia Fiscal al Consumidor Ley 27.743) — nunca dependen de un tema/branding para ser
válidos.

Este módulo devuelve HTML (string), no PDF — no carga la dependencia de un motor de render
(Playwright/Chromium). Convertir a PDF, firmarlo/protegerlo (`arca_fe.seguridad.asegurar_pdf`) y
decidir el canal de entrega (descarga, mail, portal) es responsabilidad del consumidor.
"""
from __future__ import annotations

import html as _html
import os
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

from .modelos import (
    IVA_0,
    IVA_10_5,
    IVA_21,
    IVA_27,
    CbteTipo,
    ComprobanteFiscal,
    DocTipo,
    Receptor,
    es_nota_credito,
    letra_comprobante,
)
from .qr import qr_svg
from .validadores import formatear_cuit

# ---------------------------------------------------------------------------
# Helpers de formato
# ---------------------------------------------------------------------------


def _money(n) -> str:
    """'$ 217.800,00' — 2 decimales (estándar AFIP)."""
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


def _alicuotas_iva_pct() -> tuple[float, ...]:
    return tuple(float(a.pct) for a in (IVA_0, IVA_10_5, IVA_21, IVA_27))


def _iva_pct_label(imp_neto, imp_iva) -> str:
    """% de IVA a mostrar, DERIVADO de los importes reales de la factura (no un valor fijo)."""
    if not imp_neto:
        return "21%"
    pct_crudo = float(imp_iva) / float(imp_neto) * 100
    pct = min(_alicuotas_iva_pct(), key=lambda p: abs(p - pct_crudo))
    texto = f"{pct:.1f}".rstrip("0").rstrip(".").replace(".", ",")
    return f"{texto}%"


def _receptor_doc_nro_fmt(receptor: Receptor) -> str:
    """CUIT/CUIL con guiones (`XX-XXXXXXXX-X`); DNI/Consumidor Final tal cual (no son un CUIT de
    11 dígitos, formatear_cuit no aplica)."""
    if receptor.doc_tipo in (DocTipo.CUIT, DocTipo.CUIL):
        try:
            return formatear_cuit(receptor.doc_nro)
        except ValueError:
            return str(receptor.doc_nro)
    if receptor.doc_tipo == DocTipo.CONSUMIDOR_FINAL and not receptor.doc_nro:
        return "—"
    return str(receptor.doc_nro)


def _emisor_cuit_fmt(raw: str) -> str:
    """CUIT del emisor con guiones si normaliza bien; el crudo (o "—") si no — el emisor viene de
    una consulta de configuración aparte que puede estar incompleta/desactualizada, nunca debe
    romper el render de una factura ya emitida."""
    if not raw:
        return "—"
    try:
        return formatear_cuit(raw)
    except ValueError:
        return raw


def _transparencia_fiscal_lines(f: dict) -> tuple[str, str, str]:
    """Texto de la leyenda de Transparencia Fiscal al Consumidor (Ley 27.743 / RG 5614), con los
    importes REALES de la factura — nunca hardcodeados."""
    return (
        "Régimen de Transparencia Fiscal al Consumidor (Ley 27.743)",
        f"IVA Contenido: {f['tot']['ivaStr']}",
        f"Otros Impuestos Nacionales Indirectos: {f['tot']['otrosStr']}",
    )


def _qr_img(url: str, size: int) -> str:
    """SVG inline (vectorial — no se pixela en ningún zoom), envuelto en un link clickeable al
    mismo `url` que codifica el QR — quien no pueda escanearlo puede abrir el link a mano y
    verificar el comprobante igual. Nunca atrapa errores: si `segno` no puede generarlo, el caller
    tiene que fallar fuerte, no entregar un comprobante con un hueco donde debería ir el QR exigido
    por RG4892."""
    svg = qr_svg(url, size)
    svg = svg.replace("<svg ", '<svg style="display:block" ', 1)
    return f'<a href="{_e(url)}" style="display:block;">{svg}</a>'


# ---------------------------------------------------------------------------
# Logo ARCA (SVG inline, `fill=currentColor` para teñir por contexto) — agnóstico de marca: es el
# isologo oficial de la AGENCIA (ex-AFIP), no del emisor. Playwright renderiza con base
# `about:blank`: todo va embebido, nada de `<img src="archivo-relativo">`.
# ---------------------------------------------------------------------------

_ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")


@lru_cache(maxsize=1)
def _arca_logo_svg() -> str:
    try:
        with open(os.path.join(_ASSETS_DIR, "arca-logo.svg"), encoding="utf-8") as fh:
            svg = fh.read()
    except OSError:
        return ""
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
# Layout "simplificada" — tamaño de página fijo 4:5, mínimo 1080×1350
# ---------------------------------------------------------------------------

# La simplificada es una TARJETA de esquinas redondeadas flotando sobre un fondo (no un rectángulo
# a página completa) — el ancho de página incluye el margen visible alrededor de la tarjeta en los
# 4 lados. Proporción 4:5 FIJA (identidad visual): header/CAE/info/emisor-receptor arriba y
# QR/total/leyendas abajo quedan anclados en su lugar; lo único que se ajusta con la cantidad de
# conceptos es el espacio del medio — la tarjeta en sí nunca cambia de alto.
#
# El diseño (fuentes/paddings/radios de acá abajo) está afinado en unidades "nativas" (tarjeta de
# 640px) — no se re-tocan a mano para exportar más grande. En cambio, `.page` en el HTML de más
# abajo declara ESTE tamaño nativo pero le suma `zoom:{_SIMPLIFICADA_ZOOM}`: Chromium reescala TODO
# el árbol (fuentes, radios, el QR, todo) proporcionalmente antes de imprimir/capturar, así el
# export siempre sale al tamaño mínimo pedido (1080×1350, equivalente a un post vertical de
# Instagram) sin que el diseño interno tenga que conocer ese número.
_SIMPLIFICADA_DISENO_ANCHO = 640
_SIMPLIFICADA_DISENO_MARGEN = 24
_SIMPLIFICADA_FONDO = "#f4f2ef"
_SIMPLIFICADA_DISENO_PAGE_ANCHO = _SIMPLIFICADA_DISENO_ANCHO + 2 * _SIMPLIFICADA_DISENO_MARGEN
_SIMPLIFICADA_DISENO_PAGE_ALTO = round(_SIMPLIFICADA_DISENO_PAGE_ANCHO * 5 / 4)  # ancho:alto = 4:5
_SIMPLIFICADA_DISENO_CARD_ALTO = _SIMPLIFICADA_DISENO_PAGE_ALTO - 2 * _SIMPLIFICADA_DISENO_MARGEN

# Tamaño MÍNIMO de export pedido por el dueño (equivalente a un post vertical de Instagram) — 4:5
# exacto (1080:1350). Es lo que se le pide a Playwright como página/viewport; el `zoom` de arriba
# hace que el diseño nativo (afinado en 640px) llene exactamente este tamaño.
SIMPLIFICADA_PAGE_WIDTH = 1080
SIMPLIFICADA_PAGE_HEIGHT = 1350
_SIMPLIFICADA_ZOOM = SIMPLIFICADA_PAGE_WIDTH / _SIMPLIFICADA_DISENO_PAGE_ANCHO


def tamano_pagina_layout(layout: str) -> tuple[int, int | None] | None:
    """Tamaño de página para convertir el HTML a PDF/imagen (ej. `page.pdf(...)`/
    `page.screenshot(...)` de Playwright). `None` → A4 (default, `oficial`/`detallada`). Un tuple →
    tamaño propio en píxeles (`simplificada`: 1080×1350, proporción 4:5 fija)."""
    return (
        (SIMPLIFICADA_PAGE_WIDTH, SIMPLIFICADA_PAGE_HEIGHT) if layout == "simplificada" else None
    )


def nombre_fiscal_comprobante(cbte_tipo: CbteTipo, pto_vta: int, numero: int) -> str:
    """'A-00003-00000042' — letra + punto de venta + número, formato fiscal puro. Sin prefijo de
    negocio ("Factura"/"Nota de Crédito") ni extensión de archivo — eso es una decisión de
    presentación del caller (ver `es_nota_credito` para decidir el prefijo)."""
    return f"{letra_comprobante(cbte_tipo)}-{pto_vta:05d}-{numero:08d}"


# ---------------------------------------------------------------------------
# Contexto único (mismo dato para los 3 layouts)
# ---------------------------------------------------------------------------


def _conceptos_ctx(items) -> list[dict]:
    return [
        {
            "codigo": it.codigo,
            "desc": it.descripcion,
            "detalle": it.detalle,
            "cant": _plain(it.cantidad),
            "uMedida": it.unidad_medida,
            "bonif": _plain(it.bonificacion_pct),
            "precioUnitFmt": _plain(it.precio_unitario),
            "subtotalFmt": _plain(it.subtotal),
            "importeStr": _money(it.subtotal),
        }
        for it in items
    ]


def _build_ctx(datos: ComprobanteFiscal) -> dict:
    letra = letra_comprobante(datos.cbte_tipo)
    es_nc = es_nota_credito(datos.cbte_tipo)
    cod = f"{int(datos.cbte_tipo):02d}"

    mostrar_iva = letra in ("A", "B") and datos.importe_iva > 0
    # Ley 27.743 / RG 5614: leyenda de Transparencia Fiscal al Consumidor, obligatoria en toda
    # venta/locación/prestación A CONSUMIDOR FINAL — acá eso son las Facturas B/C (la A es
    # RI-a-RI, no consumidor final por definición, fuera del alcance de la norma).
    transparencia_fiscal = letra in ("B", "C")

    return {
        "letra": letra, "cod": cod, "es_nc": es_nc, "concepto": datos.concepto_label,
        "titulo": ("NOTA DE CRÉDITO " if es_nc else "FACTURA ") + letra,
        "emisor": {
            "razonSocial": datos.emisor_razon_social or "—",
            "cuit": _emisor_cuit_fmt(datos.emisor_cuit),
            "cond": datos.emisor_condicion_iva_label,
            "dom": datos.emisor_domicilio or "—",
            "iibb": datos.emisor_iibb,
            "inicio": _fdate(datos.emisor_inicio_actividades),
            "ptoVta": f"{datos.pto_vta:05d}",
        },
        "comp": {"nro": f"{datos.numero:08d}", "fecha": _fdate(datos.fecha_emision)},
        "periodo": {
            "desde": _fdate(datos.periodo_desde),
            "hasta": _fdate(datos.periodo_hasta),
            "vto": _fdate(datos.vencimiento_pago),
        },
        "receptor": {
            "nombre": datos.receptor_nombre or "—",
            "docLabel": datos.doc_tipo_label,
            "docNro": _receptor_doc_nro_fmt(datos.receptor),
            "cond": datos.condicion_iva_receptor_label,
            "dom": datos.receptor_domicilio or "—",
            "venta": datos.condicion_venta,
        },
        "conceptos": _conceptos_ctx(datos.items),
        "tot": {
            "discrimina": mostrar_iva,
            "transparencia": transparencia_fiscal,
            "netoStr": _money(datos.importe_neto), "ivaStr": _money(datos.importe_iva),
            "subStr": _money(datos.importe_neto), "otrosStr": _money(datos.importe_otros_tributos),
            "totalStr": _money(datos.importe_total),
            "ivaPct": _iva_pct_label(datos.importe_neto, datos.importe_iva),
        },
        "cae": {"nro": datos.cae, "vto": _fdate(datos.cae_vto)},
        "qr": {"url": datos.qr_url},
    }


# ---------------------------------------------------------------------------
# 1a — Oficial, A4 (réplica fiel del comprobante oficial AFIP/ARCA)
# ---------------------------------------------------------------------------


def _factura_oficial_html(f: dict, fonts_css: str) -> str:
    qr_block = _qr_img(f["qr"]["url"], 112)

    iibb_line = (
        f'<div style="margin-bottom:4px;"><span style="font-weight:700;">Ingresos Brutos:</span> {_e(f["emisor"]["iibb"])}</div>'
        if f["emisor"]["iibb"] else ""
    )
    inicio_line = (
        f'<div><span style="font-weight:700;">Fecha de Inicio de Actividades:</span> {_e(f["emisor"]["inicio"])}</div>'
        if f["emisor"]["inicio"] else ""
    )

    transparencia_block = ""
    if f["tot"]["transparencia"]:
        titulo_tf, iva_tf, otros_tf = _transparencia_fiscal_lines(f)
        transparencia_block = f"""
        <div style="margin-top:10px;font-size:8px;line-height:1.5;">
          <div style="font-weight:700;">{_e(titulo_tf)}</div>
          <div>{_e(iva_tf)}</div>
          <div>{_e(otros_tf)}</div>
        </div>"""

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
            <div style="margin-top:10px;font-size:9px;color:#333;">Comprobante Autorizado — Verifique la validez de este comprobante en <a href="{_e(f['qr']['url'])}" style="color:#333;">www.arca.gob.ar</a></div>
            <div style="margin-top:4px;font-size:9px;color:#333;">Pág. 1/1</div>
            {transparencia_block}
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
# 1b — Simplificada (comprobante vertical compacto, para compartir por WhatsApp)
# ---------------------------------------------------------------------------


def _factura_simplificada_html(f: dict, fonts_css: str) -> str:
    tipo_txt = "Nota de crédito" if f["es_nc"] else "Factura"

    qr_block = _qr_img(f["qr"]["url"], 165)

    conceptos_html = "".join(f"""
        <div style="padding:10px 0;border-top:1px solid #eef1f4;display:flex;justify-content:space-between;gap:16px;">
          <span style="font-size:16px;font-weight:700;">{_e(c['desc'])}</span>
          <span style="font-size:16px;font-weight:700;font-variant-numeric:tabular-nums;white-space:nowrap;">{_e(c['importeStr'])}</span>
        </div>""" for c in f["conceptos"])

    iibb_line = (
        f'<div style="font-size:12px;color:#5b6875;margin-top:2px;">IIBB {_e(f["emisor"]["iibb"])}</div>'
        if f["emisor"]["iibb"] else ""
    )

    if f["tot"]["discrimina"]:
        totales_iva = f"""
        <div style="display:flex;justify-content:space-between;gap:24px;font-size:14px;color:#5b6875;padding:2px 0;"><span>Neto gravado</span><span style="font-variant-numeric:tabular-nums;">{_e(f['tot']['netoStr'])}</span></div>
        <div style="display:flex;justify-content:space-between;gap:24px;font-size:14px;color:#5b6875;padding:2px 0;"><span>IVA {_e(f['tot']['ivaPct'])}</span><span style="font-variant-numeric:tabular-nums;">{_e(f['tot']['ivaStr'])}</span></div>
        <div style="height:2px;background:#c9d0d6;margin:6px 0;"></div>"""
    else:
        totales_iva = ""

    inicio_cell = (
        '<div><div style="font-family:\'JetBrains Mono\',monospace;font-size:9px;letter-spacing:0.08em;'
        'text-transform:uppercase;color:#98a3ae;line-height:1;">Inicio de actividades</div>'
        f'<div style="font-size:14px;font-weight:600;margin-top:3px;font-variant-numeric:tabular-nums;">{_e(f["emisor"]["inicio"])}</div></div>'
        if f["emisor"]["inicio"] else ""
    )

    transparencia_block = ""
    if f["tot"]["transparencia"]:
        titulo_tf, iva_tf, otros_tf = _transparencia_fiscal_lines(f)
        transparencia_block = f"""
      <div style="margin-top:12px;padding-top:12px;border-top:1px solid #e6e9ec;font-size:10.5px;color:#98a3ae;line-height:1.5;">
        <div style="font-weight:700;color:#5b6875;">{_e(titulo_tf)}</div>
        <div>{_e(iva_tf)}</div>
        <div>{_e(otros_tf)}</div>
      </div>"""

    body = f"""
    <div style="padding:24px 28px 0;display:flex;align-items:flex-start;justify-content:space-between;gap:16px;">
      <div style="width:170px;color:#16202b;padding-top:4px;">{_arca_logo(170)}</div>
      <div style="flex:none;display:flex;align-items:center;gap:14px;">
        <div style="text-align:right;">
          <div style="font-size:20px;font-weight:800;letter-spacing:-0.01em;line-height:1.1;">{_e(tipo_txt.upper())}</div>
          <div style="font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:0.1em;text-transform:uppercase;color:#98a3ae;margin-top:2px;">Cód. {_e(f['cod'])}</div>
        </div>
        <div style="flex:none;display:flex;align-items:center;justify-content:center;width:64px;height:64px;border:1.5px solid #16202b;border-radius:10px;overflow:hidden;">
          <span style="font-size:44px;font-weight:800;line-height:1;">{_e(f['letra'])}</span>
        </div>
      </div>
    </div>

    <div style="margin:18px 28px 0;background:#f7f8fa;border-radius:10px;text-align:center;font-size:14px;padding:10px;">
      CAE N° <span style="font-weight:700;font-variant-numeric:tabular-nums;">{_e(f['cae']['nro'])}</span> · Vto. CAE <span style="font-weight:700;font-variant-numeric:tabular-nums;">{_e(f['cae']['vto'])}</span>
    </div>

    <div style="padding:16px 28px;border-bottom:1px solid #eef1f4;display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px 16px;">
      <div><div style="font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:0.08em;text-transform:uppercase;color:#98a3ae;line-height:1;">Fecha de emisión</div><div style="font-size:14px;font-weight:600;margin-top:3px;font-variant-numeric:tabular-nums;">{_e(f['comp']['fecha'])}</div></div>
      <div><div style="font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:0.08em;text-transform:uppercase;color:#98a3ae;line-height:1;">Vto. de pago</div><div style="font-size:14px;font-weight:600;margin-top:3px;font-variant-numeric:tabular-nums;">{_e(f['periodo']['vto'])}</div></div>
      <div><div style="font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:0.08em;text-transform:uppercase;color:#98a3ae;line-height:1;">Período facturado</div><div style="font-size:14px;font-weight:600;margin-top:3px;font-variant-numeric:tabular-nums;">{_e(f['periodo']['desde'])} → {_e(f['periodo']['hasta'])}</div></div>
      <div><div style="font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:0.08em;text-transform:uppercase;color:#98a3ae;line-height:1;">Punto de venta</div><div style="font-size:14px;font-weight:600;margin-top:3px;font-variant-numeric:tabular-nums;">{_e(f['emisor']['ptoVta'])}</div></div>
      <div><div style="font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:0.08em;text-transform:uppercase;color:#98a3ae;line-height:1;">Comp. Nro</div><div style="font-size:14px;font-weight:600;margin-top:3px;font-variant-numeric:tabular-nums;">{_e(f['comp']['nro'])}</div></div>
      {inicio_cell}
    </div>

    <div style="padding:16px 28px;border-bottom:1px solid #eef1f4;display:grid;grid-template-columns:1fr 1fr;gap:20px;">
      <div>
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;">
          <span style="width:6px;height:6px;border-radius:999px;background:#1c5fb8;flex:none;"></span>
          <span style="font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:0.1em;text-transform:uppercase;color:#98a3ae;">Emisor</span>
        </div>
        <div style="font-size:19px;font-weight:800;line-height:1.15;">{_e(f['emisor']['razonSocial'])}</div>
        <div style="font-size:13px;color:#5b6875;margin-top:4px;">CUIT <span style="font-weight:600;color:#16202b;font-variant-numeric:tabular-nums;">{_e(f['emisor']['cuit'])}</span> · {_e(f['emisor']['cond'])}</div>
        <div style="font-size:13px;color:#5b6875;margin-top:2px;">{_e(f['emisor']['dom'])}</div>
        {iibb_line}
      </div>
      <div>
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;">
          <span style="width:6px;height:6px;border-radius:999px;background:#16202b;flex:none;"></span>
          <span style="font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:0.1em;text-transform:uppercase;color:#98a3ae;">Receptor</span>
        </div>
        <div style="font-size:19px;font-weight:800;line-height:1.15;">{_e(f['receptor']['nombre'])}</div>
        <div style="font-size:13px;color:#5b6875;margin-top:4px;">{_e(f['receptor']['docLabel'])} <span style="font-weight:600;color:#16202b;font-variant-numeric:tabular-nums;">{_e(f['receptor']['docNro'])}</span> · {_e(f['receptor']['cond'])}</div>
        <div style="font-size:13px;color:#5b6875;margin-top:2px;">{_e(f['receptor']['dom'])}</div>
        <div style="font-size:13px;color:#5b6875;margin-top:2px;">Cond. venta: {_e(f['receptor']['venta'])}</div>
      </div>
    </div>

    <div style="padding:16px 28px;border-bottom:1px solid #eef1f4;flex:1;min-height:0;overflow:hidden;">
      <div style="font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:0.1em;text-transform:uppercase;color:#98a3ae;">Conceptos · <span style="color:#16202b;">{_e(f['concepto'])}</span></div>
      {conceptos_html}
    </div>

    <div style="padding:20px 28px 24px;background:#f7f8fa;">
      <div style="display:flex;gap:20px;align-items:flex-start;">
        <div style="flex:none;background:#fff;border:1px solid #e6e9ec;border-radius:12px;padding:8px;">{qr_block}</div>
        <div style="flex:1;min-width:0;">{totales_iva}
          <div style="display:flex;justify-content:space-between;align-items:baseline;gap:16px;">
            <span style="font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:0.1em;text-transform:uppercase;color:#98a3ae;">Total</span>
            <span style="font-size:34px;font-weight:800;letter-spacing:-0.02em;font-variant-numeric:tabular-nums;">{_e(f['tot']['totalStr'])}</span>
          </div>
          <div style="margin-top:14px;font-size:11.5px;color:#98a3ae;line-height:1.4;">
            Comprobante autorizado por ARCA · Verificá la validez escaneando el QR o en <a href="{_e(f['qr']['url'])}" style="color:#5b6875;font-weight:600;">www.arca.gob.ar</a>
          </div>
          {transparencia_block}
        </div>
      </div>
    </div>
"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width">
{fonts_css}
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  html,body {{ height:100%; background:{_SIMPLIFICADA_FONDO}; }}
  body {{ min-height:100vh; display:flex; align-items:center; justify-content:center;
          font-family:'TT Commons',ui-sans-serif,sans-serif; color:#16202b; }}
  /* El diseño está afinado en unidades NATIVAS (tarjeta de {_SIMPLIFICADA_DISENO_ANCHO}px) — acá
     `.page` declara ese tamaño nativo y le suma `zoom:{_SIMPLIFICADA_ZOOM}`, que Chromium aplica a
     TODO el árbol (fuentes, radios, el QR) antes de imprimir/capturar: el resultado siempre sale a
     {SIMPLIFICADA_PAGE_WIDTH}×{SIMPLIFICADA_PAGE_HEIGHT} (el mínimo pedido), sin re-tocar un solo
     valor de fuente/padding de acá abajo. El `transform: scale()` es un mecanismo APARTE: ajusta la
     tarjeta YA ampliada al viewport SOLO cuando se ve como preview en una ventana de otro tamaño
     (ahí 100vh/100vw igualan el tamaño de export exacto y el scale da 1, sin afectar el PDF/imagen
     final) — llena el alto/ancho disponible sin perder la proporción 4:5. */
  .page {{ flex:none; width:{_SIMPLIFICADA_DISENO_PAGE_ANCHO}px; height:{_SIMPLIFICADA_DISENO_PAGE_ALTO}px;
           padding:{_SIMPLIFICADA_DISENO_MARGEN}px; zoom:{_SIMPLIFICADA_ZOOM};
           transform:scale(min(calc(100vh / {SIMPLIFICADA_PAGE_HEIGHT}px), calc(100vw / {SIMPLIFICADA_PAGE_WIDTH}px))); }}
  .card {{ width:{_SIMPLIFICADA_DISENO_ANCHO}px; height:{_SIMPLIFICADA_DISENO_CARD_ALTO}px; display:flex; flex-direction:column;
           background:#fff; border-radius:28px; border:1px solid #ecebe8;
           box-shadow:0 1px 3px rgba(22,32,43,0.06); overflow:hidden; }}
</style>
</head>
<body><div class="page"><div class="card">{body}</div></div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# 1c — Detallada, A4 (identidad visual de la simplificada, alternativa a la oficial)
# ---------------------------------------------------------------------------


def _factura_detallada_html(f: dict, fonts_css: str) -> str:
    tipo_banner = "Nota de crédito electrónica · Original" if f["es_nc"] else "Factura electrónica · Original"

    qr_block = _qr_img(f["qr"]["url"], 150)

    iibb_line = (
        f'<div><span style="font-weight:600;color:#16202b;">Ingresos Brutos:</span> {_e(f["emisor"]["iibb"])}</div>'
        if f["emisor"]["iibb"] else ""
    )
    inicio_line = (
        f'<div><span style="font-weight:600;color:#16202b;">Inicio de Actividades:</span> {_e(f["emisor"]["inicio"])}</div>'
        if f["emisor"]["inicio"] else ""
    )

    transparencia_block = ""
    if f["tot"]["transparencia"]:
        titulo_tf, iva_tf, otros_tf = _transparencia_fiscal_lines(f)
        transparencia_block = f"""
            <div style="margin-top:14px;padding-top:14px;border-top:1px solid #eef1f4;font-size:12.5px;color:#8a97a3;line-height:1.5;">
              <div style="font-weight:700;color:#5b6875;">{_e(titulo_tf)}</div>
              <div>{_e(iva_tf)}</div>
              <div>{_e(otros_tf)}</div>
            </div>"""

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
            <div style="font-size:13px;color:#8a97a3;line-height:1.45;">Verificá la validez de este comprobante escaneando el QR o en <a href="{_e(f['qr']['url'])}" style="color:#8a97a3;">www.arca.gob.ar</a></div>
            {transparencia_block}
          </div>
        </div>
"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width">
{fonts_css}
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
    "oficial": _factura_oficial_html,
    "detallada": _factura_detallada_html,
    "simplificada": _factura_simplificada_html,
}


@dataclass(frozen=True)
class LayoutInfo:
    """Metadata de un layout, pensada para que el consumidor arme un selector real (dropdown,
    radio group) con estas mismas `nombre`/`descripcion` — en vez de inventar copy propio que
    puede desalinearse de lo que el layout realmente renderiza.

    `id`: el valor que se le pasa a `renderizar_comprobante_html(layout=...)`.
    `nombre`: label corto para mostrar al usuario.
    `descripcion`: qué es y para qué sirve, en 1-2 oraciones.
    `advertencia`: cuándo NO usarlo — vacío si no aplica a este layout."""

    id: str
    nombre: str
    descripcion: str
    advertencia: str = ""


# Orden: los dos de detalle completo primero, la simplificada al final — no es "la opción fácil
# por default", es un formato de comprobante distinto con una limitación real (ver advertencia).
LAYOUTS_INFO: tuple[LayoutInfo, ...] = (
    LayoutInfo(
        id="oficial",
        nombre="Oficial (réplica AFIP/ARCA)",
        descripcion=(
            "Reproduce el formulario oficial de ARCA. Formato A4, con el detalle completo de "
            "cada ítem: cantidad, unidad de medida, precio unitario y bonificación."
        ),
    ),
    LayoutInfo(
        id="detallada",
        nombre="Detallada",
        descripcion=(
            "Formato A4 con diseño propio. Mismo nivel de detalle que la Oficial (cantidad, "
            "precio unitario, bonificación) por ítem, con una presentación visual distinta."
        ),
    ),
    LayoutInfo(
        id="simplificada",
        nombre="Simplificada (para compartir)",
        descripcion=(
            f"Formato compacto, proporción 4:5 ({SIMPLIFICADA_PAGE_WIDTH}×{SIMPLIFICADA_PAGE_HEIGHT} "
            "mínimo) pensado para compartir por WhatsApp o redes. Resume cada ítem a su "
            "descripción e importe, SIN cantidad, precio unitario ni bonificación."
        ),
        advertencia=(
            "No es 'la versión para celular' de las otras dos — es un formato de comprobante "
            "distinto, pensado para operaciones simples. Un ítem con cantidad != 1, bonificación, "
            "unidad de medida no estándar o detalle adicional NO se puede renderizar en este "
            "formato — la librería lo rechaza (ValueError), no queda a criterio del usuario: "
            "elegí Oficial o Detallada para esos comprobantes."
        ),
    ),
)

LAYOUTS_VALIDOS: tuple[str, ...] = tuple(info.id for info in LAYOUTS_INFO)


def _validar_apto_para_simplificada(items) -> None:
    """La `simplificada` resume cada ítem a descripción+importe — NO muestra `cantidad`, `precio_unitario`,
    `bonificacion_pct` ni `detalle`. Antes esto era solo una advertencia en `LAYOUTS_INFO` (texto que el
    consumidor podía ignorar); ahora se hace cumplir en código: si algún ítem tiene información en esos
    campos que se perdería al ocultarlos, `renderizar_comprobante_html` RECHAZA con `ValueError` en vez de
    generar un comprobante que esconde datos reales — obliga a elegir `oficial`/`detallada` para esa
    operación en particular. Un ítem "apto" es cantidad=1, sin bonificación, sin `detalle` adicional y con
    la unidad de medida default ('unidad') — lo mínimo que puede resumirse sin perder nada real."""
    problematicos = [
        it for it in items
        if it.cantidad != 1 or it.bonificacion_pct != 0 or it.detalle or it.unidad_medida != "unidad"
    ]
    if problematicos:
        descripciones = ", ".join(f"'{it.descripcion}'" for it in problematicos)
        raise ValueError(
            "El layout 'simplificada' no admite ítems con cantidad != 1, bonificación, unidad de "
            "medida no estándar o detalle adicional — esa información se perdería al no mostrar "
            f"cantidad/precio unitario/detalle. Ítem(s) afectado(s): {descripciones}. "
            "Usá el layout 'oficial' o 'detallada' para este comprobante."
        )


def normalizar_layout(layout: str) -> str:
    """Valida un `layout` pedido por el caller contra los soportados (`LAYOUTS_VALIDOS`:
    `"oficial"`/`"detallada"`/`"simplificada"`, ver `LAYOUTS_INFO`) — desconocido o vacío cae a
    `"simplificada"`. Es el mismo fallback silencioso que ya aplicaba `renderizar_comprobante_html`
    puertas adentro; exponerlo deja que el caller lo aplique UNA vez y reuse el resultado ya
    normalizado en todo lo demás que dependa del mismo `layout` en la misma request (nombre de
    archivo, tamaño de página del PDF) — sin repetir el chequeo `if layout not in (...)` en cada
    punto de uso."""
    return layout if layout in _LAYOUTS else "simplificada"


def renderizar_comprobante_html(
    datos: ComprobanteFiscal,
    *,
    layout: str = "simplificada",
    fonts_css: str = "",
) -> str:
    """Genera el HTML completo de un comprobante (Factura A/B/C o Nota de Crédito) — preview
    rápido para mirarlo (sin pasar por un motor de PDF) o insumo para convertir a PDF/imagen.

    `datos`: el comprobante ya emitido, con CAE/QR/importes resueltos (`ComprobanteFiscal` valida
    en su construcción que no falte nada imprescindible — acá no se vuelve a chequear).
    `layout`: `"simplificada"` (default — vertical compacto 4:5, pensado para compartir; NO admite
    desglose de cantidad/precio unitario, ver `LAYOUTS_INFO`), `"oficial"` (réplica A4 del
    formulario oficial AFIP/ARCA) o `"detallada"` (A4, misma identidad visual que la simplificada
    pero con el detalle completo). Un valor desconocido cae a `"simplificada"` — usar
    `LAYOUTS_INFO` para mostrarle al usuario nombre/descripción/advertencia de cada opción antes de
    que elija, en vez de hardcodear copy propio.
    `fonts_css`: bloque `<style>@font-face{...}</style>` ya armado, para tipografías propias del
    caller (la oficial no lo usa — solo detallada/simplificada). Sin este parámetro (default
    `""`), el HTML sigue siendo válido: cae a los fallbacks de sistema ya declarados en el CSS — la
    marca nunca es requisito de validez fiscal.

    Devuelve el HTML como string; no convierte a PDF (eso es responsabilidad del caller, junto con
    `arca_fe.seguridad.asegurar_pdf` si hace falta el documento certificado).

    `ValueError` si el layout resuelto es `"simplificada"` y algún ítem de `datos.items` no es lo
    bastante simple para resumirse sin perder información (ver `_validar_apto_para_simplificada`)
    — NO es solo la `advertencia` de `LAYOUTS_INFO`, se hace cumplir acá: elegir `oficial` o
    `detallada` para ese comprobante en particular, no atajarse con la simplificada."""
    layout_resuelto = normalizar_layout(layout)
    if layout_resuelto == "simplificada":
        _validar_apto_para_simplificada(datos.items)
    builder = _LAYOUTS[layout_resuelto]
    ctx = _build_ctx(datos)
    return builder(ctx, fonts_css)
