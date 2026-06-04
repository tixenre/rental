"""
pdf.py — Generación de PDFs con Playwright.
Contiene los templates HTML y el renderer compartido.
"""

import asyncio
import html
import json
import os
import re
from datetime import datetime

from services.precios import (
    jornadas_periodo,
    es_responsable_inscripto,
    IVA_PCT,
)

# ── Datos del locador (configurar en variables de entorno) ────────────────────
OWNER_NOMBRE   = os.getenv("OWNER_NOMBRE",   "Marín Javier Santini Calarco")
OWNER_CUIL     = os.getenv("OWNER_CUIL",     "23-37389102-9")
OWNER_DIRECCION = os.getenv("OWNER_DIRECCION", "Falucho 4625, Mar del Plata")
OWNER_TELEFONO = os.getenv("OWNER_TELEFONO", "223 5909080")
OWNER_EMAIL    = os.getenv("OWNER_EMAIL",    "ramblarental@gmail.com")


def _abs_image_url(url: str | None) -> str:
    """Resuelve foto_url a URL absoluta para el PDF.

    Playwright renderiza con `page.set_content()` (base = about:blank), así
    que paths relativos (`/uploads/foo.jpg`) no resuelven contra el host
    del backend. Si la URL no es ya absoluta y tenemos FRONTEND_BASE_URL,
    la prependeamos. Si no podemos resolverla, devolvemos "" — la celda
    de la foto cae al placeholder "—" en el template.
    """
    if not url:
        return ""
    if url.startswith(("http://", "https://", "data:")):
        return url
    if url.startswith("/"):
        base = os.environ.get("FRONTEND_BASE_URL", "").rstrip("/")
        if base:
            return f"{base}{url}"
    return ""


# ── Helpers ──────────────────────────────────────────────────────────────────

_MESES = {
    "January": "enero",   "February": "febrero", "March": "marzo",
    "April":   "abril",   "May":      "mayo",     "June":  "junio",
    "July":    "julio",   "August":   "agosto",   "September": "septiembre",
    "October": "octubre", "November": "noviembre","December": "diciembre",
}

def _es_month(s: str) -> str:
    """Traduce nombres de meses de inglés a español."""
    for en, es in _MESES.items():
        s = s.replace(en, es)
    return s


def _nombre_para_pdf(item: dict, *, formal: bool = False) -> str:
    """Helper único para elegir qué nombre mostrar en un PDF.

    El rediseño del sistema de specs (docs/DISEÑO_SPECS.md) introdujo dos
    variantes calculadas por el backend:
      - `nombre_publico` (corto, ej. "Cámara Sony FX3 Montura E"): catálogo.
      - `nombre_publico_largo` (extendido, ej. "Cámara Sony FX3 · Cuerpo ·
        Montura E · Full-frame · 4K 120fps"): documentos formales.

    Para presupuesto usamos el corto; para albarán/contrato/seguro
    usamos el largo (más descriptivo, mejor para el cliente y el seguro).

    Fallback en cascada cuando el equipo todavía no tiene los nombres
    calculados (equipos legacy o sin categoría):
      formal=True : largo → corto → "marca nombre" → nombre interno
      formal=False: corto → "marca nombre" → nombre interno
    """
    publico = (item.get("nombre_publico") or "").strip()
    largo = (item.get("nombre_publico_largo") or "").strip()
    nombre = (item.get("nombre") or "").strip()
    marca = (item.get("marca") or "").strip()

    if formal:
        if largo:
            return largo
        if publico:
            return publico
    else:
        if publico:
            return publico

    # Fallback: marca + nombre interno (lo que hacía pdf.py antes).
    if marca and marca.lower() not in nombre.lower():
        return f"{marca} {nombre}".strip() or "—"
    return nombre or "—"

def _as_dt(s):
    """Coacciona a datetime. Acepta str ISO, date, datetime o None.
    Las columnas de fecha son TIMESTAMP/DATE → psycopg devuelve objetos."""
    if not s:
        return None
    if hasattr(s, "strftime"):  # ya es date/datetime
        return s
    try:
        return datetime.fromisoformat(str(s))
    except ValueError:
        return None

def _fmt_date_short(s) -> str:
    """Formatea fecha como DD/MM/YYYY. Retorna '—' si inválida o vacía."""
    if not s:
        return "—"
    d = _as_dt(s)
    return d.strftime("%d/%m/%Y") if d else str(s)

def _fmt_date_long(s) -> str:
    """Formatea fecha como '5 de marzo de 2025'. Retorna '—' si inválida."""
    if not s:
        return "—"
    d = _as_dt(s)
    return _es_month(d.strftime("%-d de %B de %Y")) if d else str(s)

def _fmt_date_long_time(s) -> str:
    """Formatea fecha+hora como '5 de marzo de 2025, 14:30'."""
    if not s:
        return "—"
    d = _as_dt(s)
    return _es_month(d.strftime("%-d de %B de %Y, %H:%M")) if d else str(s)

def _fmt_ars(n, zero_dash: bool = True) -> str:
    """Formatea número como peso argentino ('$1.234.567').
    zero_dash=True → retorna '—' para 0; False → retorna '$0'.
    """
    try:
        v = int(float(n or 0))
        if v == 0:
            return "—" if zero_dash else "$0"
        return "$" + f"{v:,}".replace(",", ".")
    except Exception:
        return str(n) if n else "—"

def _parse_valor(v) -> int:
    """Parsea un valor numérico desde string con posibles $, puntos y comas."""
    if v is None or v == "":
        return 0
    try:
        s = str(v).replace("$", "").replace(".", "").replace(",", "").strip()
        return int(float(s)) if s else 0
    except Exception:
        return 0


def _slug(s: str) -> str:
    """Convierte un texto en algo válido para nombre de archivo."""
    if not s:
        return "sin-cliente"
    s = re.sub(r"[^\w\s\-]", "", s, flags=re.UNICODE)
    s = re.sub(r"\s+", "-", s.strip())
    return s[:60] or "sin-cliente"


def _pedido_filename(pedido: dict, suffix: str = "") -> str:
    """Devuelve algo como 'R-0001_Martinez-Santiago.pdf' o '..._albaran.pdf'."""
    if pedido.get("numero_pedido"):
        num = f"R-{int(pedido['numero_pedido']):04d}"
    else:
        num = str(pedido["id"])
    cliente = _slug(pedido.get("cliente_nombre") or "")
    base = f"{num}_{cliente}"
    if suffix:
        base += f"_{suffix}"
    return f"{base}.pdf"


# Shared Chromium instance — created once, reused for every PDF request.
_playwright = None
_browser    = None
_browser_lock = asyncio.Lock()


async def _get_browser():
    global _playwright, _browser
    async with _browser_lock:
        if _browser is None or not _browser.is_connected():
            from playwright.async_api import async_playwright as _apw
            _playwright = await _apw().start()
            _browser = await _playwright.chromium.launch(
                headless=True, args=["--no-sandbox"]
            )
    return _browser


async def _render_pdf(html: str) -> bytes:
    """Renderiza un HTML como PDF A4 usando Playwright.

    Reutiliza un único proceso Chromium; abre y cierra una page por request.
    """
    browser   = await _get_browser()
    page      = await browser.new_page()
    try:
        await page.set_content(html, wait_until="networkidle")
        pdf_bytes = await page.pdf(
            format="A4",
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
            print_background=True,
        )
    finally:
        await page.close()
    return pdf_bytes


def _a4_page(margin: str = "18mm 14mm") -> str:
    """CSS `@page` que fija la hoja en **A4** para TODOS los documentos.

    El tamaño A4 es la regla compartida (requisito: todo PDF que se manda es A4);
    el margen es lo único por-documento. Fuente única — no declarar `@page` /
    tamaños de hoja ad-hoc en cada template (modularidad: una sola verdad de la
    hoja). `_render_pdf` ya rasteriza en A4; esto alinea el HTML con esa hoja para
    que el preview y la paginación coincidan."""
    return f"@page {{ size: A4; margin: {margin}; }}"


# ── Templates HTML ───────────────────────────────────────────────────────────

def _pedido_html(pedido: dict) -> str:
    """Genera el HTML del remito para convertir a PDF."""
    fmt_date = _fmt_date_long_time
    fmt_ars  = lambda n: _fmt_ars(n, zero_dash=False)

    items     = pedido.get("items", [])
    if pedido.get("numero_pedido"):
        remito_num = f"R-{pedido['numero_pedido']:04d}"
    else:
        remito_num = f"#{pedido['id']}"
    fecha_doc = _es_month(datetime.now().strftime("%-d de %B de %Y"))

    try:
        d1 = _as_dt(pedido["fecha_desde"])
        d2 = _as_dt(pedido["fecha_hasta"])
        jornadas = jornadas_periodo(d1, d2)
    except Exception:
        jornadas = 1

    estado_color = {
        "borrador":   "#888888",
        "presupuesto":"#f59e0b",
        "confirmado": "#22c55e",
        "retirado":   "#3b82f6",
        "devuelto":   "#a855f7",
        "cancelado":  "#ef4444",
    }.get(pedido.get("estado",""), "#888")

    rows = ""
    for it in items:
        subtotal = (it.get("precio_jornada") or 0) * it.get("cantidad",1) * jornadas
        # Presupuesto = nombre corto. Fallback al interno si no hay público aún.
        it_nombre = html.escape(_nombre_para_pdf(it, formal=False))
        foto_html = ""
        foto_abs = _abs_image_url(it.get("foto_url"))
        if foto_abs:
            foto_html = f'<img src="{html.escape(foto_abs)}" class="item-img" alt="foto">'
        else:
            foto_html = '<div class="item-img" style="display:flex;align-items:center;justify-content:center;font-size:20px">—</div>'
        rows += f"""
        <tr>
          <td style="padding:8px">{foto_html}</td>
          <td>{it_nombre}</td>
          <td class="center">{it.get("cantidad",1)}</td>
          <td class="right">{fmt_ars(it.get("precio_jornada"))}</td>
          <td class="right">{fmt_ars(subtotal)}</td>
        </tr>"""

        # Agregar componentes indentados si existen
        componentes = it.get("componentes", [])
        for comp in componentes:
            cant_comp = comp.get("cantidad",1) * it.get("cantidad",1)
            comp_subtotal = (comp.get("precio_jornada") or 0) * cant_comp * jornadas
            comp_nombre = html.escape(_nombre_para_pdf(comp, formal=False))
            comp_foto_html = ""
            comp_foto_abs = _abs_image_url(comp.get("foto_url"))
            if comp_foto_abs:
                comp_foto_html = f'<img src="{html.escape(comp_foto_abs)}" class="item-img" alt="foto">'
            else:
                comp_foto_html = '<div class="item-img" style="display:flex;align-items:center;justify-content:center;font-size:14px">—</div>'
            rows += f"""
        <tr style="opacity:0.75">
          <td style="padding:8px;padding-left:40px">{comp_foto_html}</td>
          <td style="padding-left:32px">└─ {comp_nombre}</td>
          <td class="center">{cant_comp}</td>
          <td class="right">{fmt_ars(comp.get("precio_jornada"))}</td>
          <td class="right">{fmt_ars(comp_subtotal)}</td>
        </tr>"""

    # ── Resumen de precios ────────────────────────────────────────────────
    # Fuente de verdad ÚNICA: `services/precios.calcular_total`, ya aplicada en
    # `_enriquecer_pedido_con_total` (endpoint admin) y en `_load_pedido_para_pdf`
    # (portal cliente). El PDF sólo PINTA el desglose — no recomputa la fórmula.
    # Si por algún caller faltara el desglose, caemos al neto persistido
    # (`monto_total`) y derivamos lo mínimo, para no romper (#502).
    es_ri = es_responsable_inscripto(pedido.get("cliente_perfil_impuestos"))
    iva_pct = int(pedido.get("iva_pct") or IVA_PCT)
    total_neto = int(
        pedido["monto_neto"] if pedido.get("monto_neto") is not None
        else (pedido.get("monto_total") or 0)
    )
    bruto = int(pedido.get("bruto") or total_neto)
    descuento_pct = float(pedido.get("descuento_pct") or 0)
    descuento_monto = int(
        pedido["descuento_monto"] if pedido.get("descuento_monto") is not None
        else max(0, bruto - total_neto)
    )
    iva_monto = int(
        pedido["iva_monto"] if pedido.get("iva_monto") is not None
        else (round(total_neto * IVA_PCT / 100) if es_ri else 0)
    )
    total_final = total_neto + iva_monto

    filas = [f"""
      <div class="total-row" style="opacity:0.85">
        <span class="total-label">Subtotal</span>
        <span class="total-val">{fmt_ars(bruto)}</span>
      </div>"""]
    if descuento_monto > 0:
        pct_txt = f" ({descuento_pct:g}%)" if descuento_pct else ""
        filas.append(f"""
      <div class="total-row" style="opacity:0.85">
        <span class="total-label">Descuento{pct_txt}</span>
        <span class="total-val">−{fmt_ars(descuento_monto)}</span>
      </div>""")
    if es_ri:
        if descuento_monto > 0:
            filas.append(f"""
      <div class="total-row" style="opacity:0.85">
        <span class="total-label">Neto</span>
        <span class="total-val">{fmt_ars(total_neto)}</span>
      </div>""")
        filas.append(f"""
      <div class="total-row" style="opacity:0.85">
        <span class="total-label">IVA {iva_pct}%</span>
        <span class="total-val">{fmt_ars(iva_monto)}</span>
      </div>""")
    filas.append(f"""
      <div class="total-row">
        <span class="total-label">Total</span>
        <span class="total-val">{fmt_ars(total_final)}</span>
      </div>""")
    if not es_ri:
        filas.append("""
      <div class="total-row" style="opacity:0.55;font-size:11px">
        <span class="total-label">IVA no discriminado</span>
        <span class="total-val"></span>
      </div>""")
    totales_html = "".join(filas)

    notas_html = f'<div class="notas"><strong>Notas:</strong> {html.escape(pedido["notas"])}</div>' \
                 if pedido.get("notas") else ""

    cliente_extra = ""
    if pedido.get("cliente_email"):
        cliente_extra += f'<div>{html.escape(pedido["cliente_email"])}</div>'
    if pedido.get("cliente_telefono"):
        cliente_extra += f'<div>{html.escape(pedido["cliente_telefono"])}</div>'

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800;900&family=Space+Mono:wght@400;700&display=swap');

  {_a4_page(margin="0")}

  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: 'Space Mono', monospace;
    font-size: 11px;
    color: #1a1a1a;
    background: #fff;
    padding: 0;
  }}

  .page {{
    width: 794px;
    min-height: 1123px;
    margin: 0 auto;
    padding: 52px 56px;
    display: flex;
    flex-direction: column;
  }}

  .header {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding-bottom: 28px;
    border-bottom: 2px solid #1a1a1a;
    margin-bottom: 32px;
  }}
  .logo {{
    font-family: 'Nunito', sans-serif;
    font-weight: 900;
    font-size: 28px;
    letter-spacing: -.03em;
    line-height: 1;
  }}
  .logo em {{ color: #F9B92E; font-style: normal; }}
  .logo-sub {{
    font-family: 'Space Mono', monospace;
    font-size: 9px;
    color: #888;
    letter-spacing: .12em;
    text-transform: uppercase;
    margin-top: 4px;
  }}
  .doc-info {{ text-align: right; }}
  .doc-type {{
    font-family: 'Nunito', sans-serif;
    font-weight: 800;
    font-size: 20px;
    color: #1a1a1a;
    text-transform: uppercase;
    letter-spacing: .04em;
  }}
  .doc-num {{
    font-size: 13px;
    color: #F9B92E;
    font-weight: 700;
    margin-top: 2px;
  }}
  .doc-date {{ font-size: 10px; color: #888; margin-top: 4px; }}
  .estado-badge {{
    display: inline-block;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: .1em;
    text-transform: uppercase;
    padding: 3px 10px;
    border-radius: 20px;
    color: #fff;
    background: {estado_color};
    margin-top: 8px;
  }}

  .meta {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
    margin-bottom: 32px;
  }}
  .meta-block {{ display: flex; flex-direction: column; gap: 4px; }}
  .meta-label {{
    font-size: 8px;
    color: #aaa;
    letter-spacing: .14em;
    text-transform: uppercase;
    margin-bottom: 2px;
  }}
  .meta-val {{
    font-family: 'Nunito', sans-serif;
    font-weight: 700;
    font-size: 14px;
    color: #1a1a1a;
    line-height: 1.3;
  }}
  .meta-sub {{ font-size: 10px; color: #555; }}

  .items-table {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 0;
  }}
  .items-table th {{
    font-size: 8px;
    letter-spacing: .12em;
    text-transform: uppercase;
    color: #888;
    padding: 8px 10px;
    border-bottom: 1px solid #e5e5e5;
    text-align: left;
    font-weight: 400;
  }}
  .items-table th.right, .items-table th.center {{ text-align: right; }}
  .items-table td {{
    padding: 11px 10px;
    border-bottom: 1px solid #f0f0f0;
    vertical-align: top;
    line-height: 1.4;
  }}
  .items-table td.right {{ text-align: right; }}
  .items-table td.center {{ text-align: center; }}
  .item-img {{ width: 48px; height: 48px; object-fit: cover; border-radius: 4px; background: #f0f0f0; }}
  .items-table tr:last-child td {{ border-bottom: 1px solid #e5e5e5; }}

  .total-section {{
    display: flex;
    justify-content: flex-end;
    margin-top: 16px;
    margin-bottom: 32px;
  }}
  .total-box {{
    background: #1a1a1a;
    color: #fff;
    border-radius: 10px;
    padding: 16px 24px;
    min-width: 220px;
  }}
  .total-row {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 32px;
  }}
  .total-label {{
    font-size: 9px;
    letter-spacing: .12em;
    text-transform: uppercase;
    color: #888;
  }}
  .total-val {{
    font-family: 'Nunito', sans-serif;
    font-weight: 900;
    font-size: 22px;
    color: #F9B92E;
  }}
  .total-sub {{
    font-size: 9px;
    color: #555;
    text-align: right;
    margin-top: 4px;
  }}

  .notas {{
    background: #f9f9f9;
    border-left: 3px solid #F9B92E;
    padding: 12px 16px;
    font-size: 10px;
    color: #555;
    border-radius: 0 6px 6px 0;
    margin-bottom: 32px;
    line-height: 1.6;
  }}

  .footer {{
    margin-top: auto;
    padding-top: 24px;
    border-top: 1px solid #e5e5e5;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 9px;
    color: #aaa;
    letter-spacing: .04em;
  }}
  .footer-brand {{ font-weight: 700; color: #888; }}
</style>
</head>
<body>
<div class="page">

  <div class="header">
    <div>
      <div class="logo"><em>Rambla</em> Rental</div>
      <div class="logo-sub">Alquiler de equipos audiovisuales</div>
    </div>
    <div class="doc-info">
      <div class="doc-type">Presupuesto</div>
      <div class="doc-num">N° {remito_num}</div>
      <div class="doc-date">Emitido el {fecha_doc}</div>
      <div><span class="estado-badge">{pedido.get("estado","").upper()}</span></div>
    </div>
  </div>

  <div class="meta">
    <div class="meta-block">
      <div class="meta-label">Cliente</div>
      <div class="meta-val">{html.escape(pedido.get("cliente_nombre") or "—")}</div>
      {cliente_extra}
    </div>
    <div class="meta-block">
      <div class="meta-label">Período de alquiler</div>
      <div class="meta-val" style="font-size:12px">{fmt_date(pedido.get("fecha_desde"))}</div>
      <div class="meta-sub">→ {fmt_date(pedido.get("fecha_hasta"))}</div>
      <div class="meta-sub" style="margin-top:4px;color:#F9B92E;font-weight:700">
        {jornadas} jornada{"s" if jornadas != 1 else ""}
      </div>
    </div>
  </div>

  <table class="items-table">
    <thead>
      <tr>
        <th style="width:60px"></th>
        <th>Equipo</th>
        <th class="center">Cant.</th>
        <th class="right">Precio / jornada</th>
        <th class="right">Subtotal</th>
      </tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>

  <div class="total-section">
    <div class="total-box">
      {totales_html}
      <div class="total-sub">{jornadas} jornada{"s" if jornadas != 1 else ""} · {len(items)} equipo{"s" if len(items) != 1 else ""}</div>
    </div>
  </div>

  {notas_html}

  <div class="footer">
    <span class="footer-brand">Rambla Rental</span>
    <span>Alquiler de equipos audiovisuales · Buenos Aires</span>
    <span>ramblarental.com.ar</span>
  </div>

</div>
</body>
</html>"""


def _albaran_html(pedido: dict) -> str:
    """HTML para el albarán: sin precios, con serie y valor de reposición."""
    fmt_date    = _fmt_date_short
    fmt_ars     = _fmt_ars
    parse_valor = _parse_valor

    items = pedido.get("items", [])
    valor_total = 0

    def _valor_celda(valor_unit: int, cantidad: int) -> str:
        """Renderiza la celda 'Valor reposición':
        - Si cantidad == 1: solo el valor (más limpio).
        - Si cantidad > 1: 'valor x cant = subtotal' explícito (issue #92,
          para que el cliente vea claro que es POR UNIDAD).
        """
        subtotal = valor_unit * cantidad
        if cantidad <= 1:
            return f'<div class="right">{fmt_ars(valor_unit)}</div>'
        return (
            f'<div class="right">'
            f'<div style="font-size:9pt;color:#666">'
            f'{fmt_ars(valor_unit)} × {cantidad} und'
            f'</div>'
            f'<div style="font-weight:600">{fmt_ars(subtotal)}</div>'
            f'</div>'
        )

    rows = ""
    n = 1
    for it in items:
        cant   = it.get("cantidad", 1)
        # Albarán = nombre largo (más descriptivo: incluye specs claves).
        # Si no hay nombre público todavía (equipo sin categoría), fallback
        # al combo viejo de marca + nombre + modelo.
        nombre_publico_largo = (it.get("nombre_publico_largo") or "").strip()
        if nombre_publico_largo:
            descripcion = html.escape(nombre_publico_largo)
        else:
            nombre_raw = it.get("nombre") or "—"
            marca  = it.get("marca") or ""
            modelo = it.get("modelo") or ""
            descripcion = nombre_raw
            if marca and marca.lower() not in nombre_raw.lower():
                descripcion = f"{marca} {nombre_raw}"
            if modelo:
                descripcion += f" — {modelo}"
            descripcion = html.escape(descripcion)
        serie  = html.escape(it.get("serie") or "—")
        valor  = parse_valor(it.get("valor_reposicion"))
        valor_total += valor * cant

        foto_html = ""
        foto_abs = _abs_image_url(it.get("foto_url"))
        if foto_abs:
            foto_html = f'<img src="{html.escape(foto_abs)}" class="alb-img" alt="foto">'
        else:
            foto_html = '<div class="alb-img" style="display:flex;align-items:center;justify-content:center;font-size:16px">—</div>'
        rows += f"""
        <tr>
          <td class="center">{n}</td>
          <td style="padding:4px">{foto_html}</td>
          <td>{descripcion}</td>
          <td class="center">{cant}</td>
          <td class="mono">{serie}</td>
          <td>{_valor_celda(valor, cant)}</td>
        </tr>"""
        n += 1

        # Agregar componentes indentados si existen
        componentes = it.get("componentes", [])
        for comp in componentes:
            comp_cant = comp.get("cantidad", 1) * cant
            # Componente: usar nombre largo si existe, sino el viejo combo.
            comp_publico_largo = (comp.get("nombre_publico_largo") or "").strip()
            if comp_publico_largo:
                comp_descripcion = html.escape(comp_publico_largo)
            else:
                comp_nombre_raw = comp.get("nombre") or "—"
                comp_marca = comp.get("marca") or ""
                comp_modelo = comp.get("modelo") or ""
                comp_descripcion = comp_nombre_raw
                if comp_marca and comp_marca.lower() not in comp_nombre_raw.lower():
                    comp_descripcion = f"{comp_marca} {comp_nombre_raw}"
                if comp_modelo:
                    comp_descripcion += f" — {comp_modelo}"
                comp_descripcion = html.escape(comp_descripcion)
            comp_serie = html.escape(comp.get("serie") or "—")
            comp_valor = parse_valor(comp.get("valor_reposicion"))
            valor_total += comp_valor * comp_cant

            comp_foto_html = ""
            comp_foto_abs = _abs_image_url(comp.get("foto_url"))
            if comp_foto_abs:
                comp_foto_html = f'<img src="{html.escape(comp_foto_abs)}" class="alb-img" alt="foto">'
            else:
                comp_foto_html = '<div class="alb-img" style="display:flex;align-items:center;justify-content:center;font-size:12px">—</div>'

            rows += f"""
        <tr style="opacity:0.75">
          <td class="center">{n}</td>
          <td style="padding:4px;padding-left:28px">{comp_foto_html}</td>
          <td style="padding-left:24px">└─ {comp_descripcion}</td>
          <td class="center">{comp_cant}</td>
          <td class="mono">{comp_serie}</td>
          <td>{_valor_celda(comp_valor, comp_cant)}</td>
        </tr>"""
            n += 1

    if pedido.get("numero_pedido"):
        ref = f"R-{int(pedido['numero_pedido']):04d}"
    else:
        ref = f"#{pedido['id']}"

    fecha_doc = datetime.now().strftime("%d/%m/%Y")

    return f"""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<style>
  {_a4_page()}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, 'Helvetica Neue', Arial, sans-serif;
    color: #111; font-size: 11pt; line-height: 1.45;
  }}
  .header {{
    display: flex; justify-content: space-between; align-items: flex-start;
    border-bottom: 2px solid #111; padding-bottom: 12px; margin-bottom: 18px;
  }}
  .logo {{
    font-family: 'Helvetica Neue', sans-serif; font-weight: 900; font-size: 22pt;
    letter-spacing: -.5px;
  }}
  .logo em {{ color: #F9B92E; font-style: normal; }}
  .doc-tipo {{
    text-align: right; font-size: 10pt; color: #444;
  }}
  .doc-tipo h1 {{
    font-size: 18pt; font-weight: 800; margin: 0; color: #111;
    text-transform: uppercase; letter-spacing: 1px;
  }}
  .meta {{
    display: grid; grid-template-columns: 1fr 1fr; gap: 14px;
    background: #f6f6f6; padding: 14px 18px; border-radius: 6px; margin-bottom: 16px;
  }}
  .meta-item {{ display: flex; flex-direction: column; gap: 3px; }}
  .meta-label {{
    font-size: 8pt; color: #666; text-transform: uppercase;
    letter-spacing: 1px; font-weight: 700;
  }}
  .meta-val {{ font-size: 11pt; font-weight: 600; }}
  .nota {{
    background: #fffbe6; border-left: 3px solid #F9B92E;
    padding: 10px 14px; font-size: 9.5pt; color: #555; margin-bottom: 16px;
  }}
  table {{
    width: 100%; border-collapse: collapse; margin-bottom: 18px;
  }}
  th {{
    background: #111; color: #fff; text-align: left;
    padding: 8px 10px; font-size: 9pt; font-weight: 700;
    text-transform: uppercase; letter-spacing: .5px;
  }}
  td {{
    padding: 8px 10px; border-bottom: 1px solid #e5e5e5; font-size: 10pt;
  }}
  td.center, th.center {{ text-align: center; }}
  td.right, th.right {{ text-align: right; }}
  td.mono {{ font-family: 'Menlo', 'Consolas', monospace; font-size: 9.5pt; }}
  .alb-img {{ width: 40px; height: 40px; object-fit: cover; border-radius: 3px; background: #f0f0f0; }}
  .totales {{
    display: flex; justify-content: flex-end; margin-top: 6px;
  }}
  .totales-box {{
    border: 1px solid #111; padding: 10px 16px; min-width: 280px;
  }}
  .totales-row {{
    display: flex; justify-content: space-between; align-items: center;
    font-size: 10pt; padding: 4px 0;
  }}
  .totales-row.final {{
    font-size: 13pt; font-weight: 800; border-top: 1px solid #111;
    padding-top: 8px; margin-top: 4px;
  }}
  .firmas {{
    display: grid; grid-template-columns: 1fr 1fr; gap: 40px;
    margin-top: 50px;
  }}
  .firma {{
    border-top: 1px solid #111; padding-top: 6px; text-align: center;
    font-size: 9pt; color: #555;
  }}
  .footer {{
    position: fixed; bottom: 8mm; left: 14mm; right: 14mm;
    text-align: center; font-size: 8pt; color: #999;
    border-top: 1px solid #ddd; padding-top: 6px;
  }}
</style>
</head>
<body>

<div class="header">
  <div>
    <div class="logo">Rambla <em>Rental</em></div>
    <div style="font-size:9pt;color:#666;margin-top:4px">Alquiler de equipos audiovisuales</div>
  </div>
  <div class="doc-tipo">
    <h1>Albarán</h1>
    <div style="margin-top:4px">Ref. {ref}</div>
    <div>Emitido: {fecha_doc}</div>
  </div>
</div>

<div class="meta">
  <div class="meta-item">
    <div class="meta-label">Cliente</div>
    <div class="meta-val">{html.escape(pedido.get("cliente_nombre") or "—")}</div>
  </div>
  <div class="meta-item">
    <div class="meta-label">Documento / contacto</div>
    <div class="meta-val" style="font-size:10pt">{html.escape(pedido.get("cliente_email") or pedido.get("cliente_telefono") or "—")}</div>
  </div>
  <div class="meta-item">
    <div class="meta-label">Retiro</div>
    <div class="meta-val">{fmt_date(pedido.get("fecha_desde"))}</div>
  </div>
  <div class="meta-item">
    <div class="meta-label">Devolución prevista</div>
    <div class="meta-val">{fmt_date(pedido.get("fecha_hasta"))}</div>
  </div>
</div>

<div class="nota">
  Este documento detalla los equipos entregados al cliente al momento del retiro,
  con su número de serie y valor de reposición. Se utiliza como referencia para
  cobertura de seguro. <strong>No incluye montos de alquiler.</strong>
</div>

<table>
  <thead>
    <tr>
      <th class="center" style="width:32px">#</th>
      <th style="width:50px"></th>
      <th>Equipo</th>
      <th class="center" style="width:60px">Cant.</th>
      <th style="width:140px">Nº Serie</th>
      <th class="right" style="width:150px">Valor reposición<br/><span style="font-size:7.5pt;opacity:0.8;font-weight:500">(por unidad)</span></th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>

<div class="totales">
  <div class="totales-box">
    <div class="totales-row">
      <span>Equipos entregados</span><strong>{sum(i.get("cantidad",1) for i in items)}</strong>
    </div>
    <div class="totales-row final">
      <span>Valor total de reposición</span><span>{fmt_ars(valor_total)}</span>
    </div>
    <div style="font-size:8.5pt;color:#666;margin-top:6px;padding-top:6px;border-top:1px dashed #ccc;text-align:right">
      Suma de cantidad × valor unitario,<br/>incluyendo componentes de kits.
    </div>
  </div>
</div>

<div class="firmas">
  <div class="firma">Firma cliente — aclaración / DNI</div>
  <div class="firma">Firma Rambla Rental</div>
</div>

<div class="footer">
  Rambla Rental · ramblarental.com.ar · Documento generado el {fecha_doc}
</div>

</body>
</html>"""


def _contrato_html(pedido: dict) -> str:
    """HTML para el contrato de alquiler con términos legales y firmas."""
    fmt_date         = _fmt_date_short
    fmt_datetime_long = _fmt_date_long
    fmt_ars          = _fmt_ars
    parse_valor      = _parse_valor

    fecha_hoy = _es_month(datetime.now().strftime("%d de %B de %Y"))
    items = pedido.get("items", [])

    # Calcular jornadas si no vienen pre-computadas — el template lo muestra
    # en el bloque "Duración" y antes quedaba "—" porque _get_alquiler_detail
    # no calculaba este campo.
    jornadas = pedido.get("cantidad_jornadas")
    if not jornadas:
        try:
            d1 = datetime.fromisoformat(pedido["fecha_desde"])
            d2 = datetime.fromisoformat(pedido["fecha_hasta"])
            jornadas = jornadas_periodo(d1, d2)
        except Exception:
            jornadas = 1

    # Tabla de equipos (mezcla de presupuesto + albarán + contrato)
    rows = ""
    for i, it in enumerate(items, 1):
        cant = it.get("cantidad", 1)
        # Contrato = nombre largo (descripción formal, para seguro/garantía).
        nombre_largo = (it.get("nombre_publico_largo") or "").strip()
        if nombre_largo:
            descripcion = html.escape(nombre_largo)
        else:
            nombre_raw = it.get("nombre") or "—"
            marca = it.get("marca") or ""
            modelo = it.get("modelo") or ""
            descripcion = nombre_raw
            if marca and marca.lower() not in nombre_raw.lower():
                descripcion = f"{marca} {nombre_raw}"
            if modelo:
                descripcion += f" — {modelo}"
            descripcion = html.escape(descripcion)
        serie = html.escape(it.get("serie") or "—")
        valor_repo = parse_valor(it.get("valor_reposicion"))
        precio_jornada = it.get("precio_jornada") or 0

        rows += f'''<tr>
          <td class="center">{i}</td>
          <td>{descripcion}</td>
          <td class="center">{cant}</td>
          <td class="mono">{serie}</td>
          <td class="right">{fmt_ars(valor_repo)}</td>
          <td class="right">${precio_jornada:g}</td>
          <td></td>
        </tr>'''

        # Agregar componentes indentados si existen
        componentes = it.get("componentes", [])
        for comp in componentes:
            comp_cant = comp.get("cantidad", 1) * cant
            comp_largo = (comp.get("nombre_publico_largo") or "").strip()
            if comp_largo:
                comp_descripcion = html.escape(comp_largo)
            else:
                comp_nombre_raw = comp.get("nombre") or "—"
                comp_marca = comp.get("marca") or ""
                comp_modelo = comp.get("modelo") or ""
                comp_descripcion = comp_nombre_raw
                if comp_marca and comp_marca.lower() not in comp_nombre_raw.lower():
                    comp_descripcion = f"{comp_marca} {comp_nombre_raw}"
                if comp_modelo:
                    comp_descripcion += f" — {comp_modelo}"
                comp_descripcion = html.escape(comp_descripcion)
            comp_serie = html.escape(comp.get("serie") or "—")
            comp_valor = parse_valor(comp.get("valor_reposicion"))
            comp_precio = comp.get("precio_jornada") or 0

            rows += f'''<tr style="opacity:0.85">
              <td class="center">—</td>
              <td style="padding-left:24px">└─ {comp_descripcion}</td>
              <td class="center">{comp_cant}</td>
              <td class="mono">{comp_serie}</td>
              <td class="right">{fmt_ars(comp_valor)}</td>
              <td class="right">${comp_precio:g}</td>
              <td></td>
            </tr>'''

    # Datos del cliente (locatario)
    cliente_nombre    = html.escape(pedido.get("cliente_nombre") or "—")
    cliente_email     = html.escape(pedido.get("cliente_email") or "—")
    cliente_telefono  = html.escape(pedido.get("cliente_telefono") or "—")
    cliente_direccion = html.escape(pedido.get("cliente_direccion") or "—")
    cliente_cuit      = html.escape(pedido.get("cliente_cuit") or "—")
    # Datos fiscales si el cliente es Responsable Inscripto (Factura A).
    es_ri = es_responsable_inscripto(pedido.get("cliente_perfil_impuestos"))
    razon_social     = html.escape(pedido.get("cliente_razon_social") or "")
    domicilio_fiscal = html.escape(pedido.get("cliente_domicilio_fiscal") or "")
    fiscal_extra_html = ""
    if es_ri:
        fiscal_extra_html = f"""
    <div class="parte-dato">
      <div class="parte-label">Razón social</div>
      <div class="parte-val">{razon_social or "—"}</div>
    </div>
    <div class="parte-dato">
      <div class="parte-label">CUIT</div>
      <div class="parte-val">{cliente_cuit}</div>
    </div>
    <div class="parte-dato">
      <div class="parte-label">Domicilio fiscal</div>
      <div class="parte-val">{domicilio_fiscal or cliente_direccion}</div>
    </div>
    <div class="parte-dato">
      <div class="parte-label">Condición IVA</div>
      <div class="parte-val">Responsable Inscripto</div>
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Contrato</title>
<style>
  {_a4_page(margin="0")}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'Space Mono', 'Courier New', monospace;
    font-size: 10pt;
    line-height: 1.6;
    color: #333;
    background: white;
  }}
  .header {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 20px;
    padding-bottom: 12px;
    border-bottom: 2px solid #333;
  }}
  .header-left {{
    display: flex;
    flex-direction: column;
  }}
  .logo {{
    font-size: 20pt;
    font-weight: bold;
    letter-spacing: -1px;
  }}
  .logo em {{
    color: #F9B92E;
    font-style: normal;
  }}
  .logo-sub {{
    font-size: 8pt;
    color: #666;
    margin-top: 2px;
  }}
  .doc-tipo {{
    text-align: right;
  }}
  .doc-titulo {{
    font-size: 18pt;
    font-weight: bold;
    margin-bottom: 4px;
  }}
  .meta {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-bottom: 16px;
    padding: 12px;
    background: #f9f9f9;
    border-radius: 4px;
  }}
  .meta-item {{
    display: flex;
    gap: 8px;
  }}
  .meta-label {{
    font-size: 8pt;
    color: #999;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-weight: bold;
    min-width: 100px;
  }}
  .meta-val {{
    font-weight: 500;
  }}
  .partes {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 20px;
  }}
  .parte {{
    padding: 12px;
    border: 1px solid #ddd;
    border-radius: 4px;
    background: #fafafa;
  }}
  .parte-titulo {{
    font-weight: bold;
    margin-bottom: 8px;
    font-size: 11pt;
    border-bottom: 1px solid #ddd;
    padding-bottom: 4px;
  }}
  .parte-dato {{
    margin-bottom: 6px;
    font-size: 9pt;
  }}
  .parte-label {{
    color: #999;
    font-size: 8pt;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}
  .parte-val {{
    margin-top: 2px;
    font-weight: 500;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 16px;
    font-size: 10pt;
  }}
  th {{
    background: #f0f0f0;
    padding: 8px;
    text-align: left;
    font-weight: bold;
    border-bottom: 2px solid #333;
    font-size: 9pt;
  }}
  td {{
    padding: 6px 8px;
    border-bottom: 1px solid #ddd;
  }}
  .center {{ text-align: center; }}
  .right {{ text-align: right; }}
  .mono {{ font-family: 'Courier New', monospace; font-size: 9pt; }}
  .contrato-texto {{
    font-size: 9pt;
    line-height: 1.8;
    text-align: justify;
    margin-bottom: 20px;
    padding: 12px;
    background: #fafafa;
    border-left: 3px solid #F9B92E;
  }}
  .contrato-clausula {{
    margin-bottom: 8px;
  }}
  .firmas {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    margin-top: 40px;
  }}
  .firma-box {{
    border-top: 1px solid #333;
    padding-top: 8px;
    text-align: center;
    font-size: 9pt;
  }}
  .firma-etiqueta {{
    color: #666;
    margin-top: 4px;
  }}
  .footer {{
    position: fixed;
    bottom: 8mm;
    left: 14mm;
    right: 14mm;
    text-align: center;
    font-size: 8pt;
    color: #999;
    border-top: 1px solid #ddd;
    padding-top: 6px;
  }}
  .page {{
    max-width: 210mm;
    height: 297mm;
    margin: 0 auto;
    padding: 14mm;
    background: white;
    page-break-after: always;
  }}
</style>
</head>
<body>

<div class="page">

<div class="header">
  <div class="header-left">
    <div class="logo">Rambla <em>Rental</em></div>
    <div class="logo-sub">Alquiler de equipos audiovisuales</div>
  </div>
  <div class="doc-tipo">
    <div class="doc-titulo">CONTRATO</div>
    <div>Ref: {pedido.get("numero_pedido") and f"R-{int(pedido.get('numero_pedido')):04d}" or str(pedido.get("id"))}</div>
    <div>Fecha: {fecha_hoy}</div>
  </div>
</div>

<div class="meta">
  <div class="meta-item">
    <span class="meta-label">Período de locación</span>
    <span class="meta-val">{fmt_date(pedido.get("fecha_desde"))} al {fmt_date(pedido.get("fecha_hasta"))}</span>
  </div>
  <div class="meta-item">
    <span class="meta-label">Duración</span>
    <span class="meta-val">{jornadas} jornadas</span>
  </div>
</div>

<div class="partes">
  <div class="parte">
    <div class="parte-titulo">LOCADOR (Parte que alquila)</div>
    <div class="parte-dato">
      <div class="parte-label">Nombre</div>
      <div class="parte-val">{html.escape(OWNER_NOMBRE)}</div>
    </div>
    <div class="parte-dato">
      <div class="parte-label">CUIL</div>
      <div class="parte-val">{html.escape(OWNER_CUIL)}</div>
    </div>
    <div class="parte-dato">
      <div class="parte-label">Domicilio</div>
      <div class="parte-val">{html.escape(OWNER_DIRECCION)}</div>
    </div>
    <div class="parte-dato">
      <div class="parte-label">Teléfono</div>
      <div class="parte-val">{html.escape(OWNER_TELEFONO)}</div>
    </div>
    <div class="parte-dato">
      <div class="parte-label">Email</div>
      <div class="parte-val">{html.escape(OWNER_EMAIL)}</div>
    </div>
  </div>

  <div class="parte">
    <div class="parte-titulo">LOCATARIO (Parte que alquila)</div>
    <div class="parte-dato">
      <div class="parte-label">Nombre</div>
      <div class="parte-val">{cliente_nombre}</div>
    </div>
    <div class="parte-dato">
      <div class="parte-label">Teléfono</div>
      <div class="parte-val">{cliente_telefono}</div>
    </div>
    <div class="parte-dato">
      <div class="parte-label">Email</div>
      <div class="parte-val">{cliente_email}</div>
    </div>
    <div class="parte-dato">
      <div class="parte-label">Domicilio</div>
      <div class="parte-val">{cliente_direccion}</div>
    </div>{fiscal_extra_html}
  </div>
</div>

<div style="margin-bottom: 16px;">
  <div style="font-weight: bold; margin-bottom: 8px; font-size: 10pt;">EQUIPOS A ALQUILAR</div>
  <table>
    <thead>
      <tr>
        <th style="width: 25px">#</th>
        <th>Equipo</th>
        <th style="width: 50px">Cantidad</th>
        <th style="width: 90px">N° Serie</th>
        <th style="width: 70px">Reposición</th>
        <th style="width: 70px">Precio/jornada</th>
        <th>Observaciones</th>
      </tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>
</div>

<div class="contrato-texto">
  <div class="contrato-clausula"><strong>El Locador y el Locatario</strong>, cuya individualización surge del frente del presente contrato de locación de cosas muebles no fungibles, resuelven celebrar el mismo de acuerdo con las normas establecidas por el art. 1499 del Código Civil, y que se regirá por las siguientes cláusulas y condiciones:</div>

  <div class="contrato-clausula"><strong>PRIMERO.</strong> El locatario declara recibir en locación los objetos que se detallan en este contrato y que forman parte del mismo de plena conformidad y en perfecto estado de funcionamiento, por haberlos probado en el acto de recepción, obligándose a su restitución en el plazo también indicado en el dorso y en las mismas condiciones de funcionamiento.</div>

  <div class="contrato-clausula"><strong>SEGUNDO.</strong> El plazo de la locación como así también su destino es el que surge del frente del presente contrato y de igual modo su precio es el establecido por las tarifas vigentes, que el locatario declara conocer.</div>

  <div class="contrato-clausula"><strong>TERCERO.</strong> Los bienes locados, objetos de este contrato, deberán ser devueltos en el plazo y domicilio indicado por la locadora.</div>

  <div class="contrato-clausula"><strong>CUARTO.</strong> En caso de incumplimiento a lo establecido en el artículo precedente, el locatario pagará a la locadora por cada día de demora, incluidos los feriados, el precio de alquiler pactado con una recarga del 50% de dicha suma. En concepto de la cláusula penal, y que se operará de pleno derecho y por mero vencimiento del plazo pactado, sin necesidad de interpelación alguna.</div>

  <div class="contrato-clausula"><strong>QUINTO.</strong> El locatario ha probado y reconoce el perfecto funcionamiento de los bienes locados, y en consecuencia, el locador no asume responsabilidad alguna sobre el resultado de los trabajos que se efectúen con dichos elementos.</div>

  <div class="contrato-clausula"><strong>SEXTO.</strong> El locatario se obliga y a su costa, a custodiar y mantener en perfectas condiciones previstas en el artículo "CUATRO" de este contrato; el locatario se obliga y a su costa reemplazo y/o reparación de las piezas y/o mecanismo y/o partes afectadas que impidan el uso normal de los equipos en cuestión y por otras legítimas de las marcas que correspondan, y las mencionadas reparaciones se efectuarán por los términos que el locador indique en la emergencia.</div>

  <div class="contrato-clausula"><strong>SÉPTIMO.</strong> Para el supuesto caso, del artículo precedente jugarán las condiciones previstas en el artículo "CUARTO" , respecto al pago de la locación, por cada día de demora y sus recargos correspondientes, hasta el día en que los elementos estén perfectamente reparados y entregados de conformidad del locador. Esto sin perjuicio del pago de las reparaciones a costa del locatario.</div>

  <div class="contrato-clausula"><strong>OCTAVO.</strong> El locatario se hace responsable por los daños y perjuicios que pudieran sufrir los bienes dados, ya sea por caso fortuito, fuerza mayor, culpa, hecho de terceros, etc. Asimismo el locatario será responsable por cualquier daño y/o perjuicio que sufran por cualquier causa emanada de los equipos alquilados, las operaciones de los mismos o terceros, y aun cuando el daño se origine en caso fortuito, fuerza mayor, hechos de terceros, etc.</div>

  <div class="contrato-clausula"><strong>NOVENO.</strong> El locatario para supuestos casos de lo previsto en el artículo precedente, o que se produzca la pérdida, destrucción o rotura de los bienes, durante el lapso de duración del contrato que impidan en el futuro el uso normal de los equipos locados se obliga a reponer cualquiera o todos los elementos que hubiera sufrido el daño o pérdida, a abonar al locador el valor de los comercios de plaza más caracterizados, o sus importadores, con la pertinentes cargas impositivas aduaneras y fletes.</div>

  <div class="contrato-clausula"><strong>DÉCIMO.</strong> El locatario se obliga a no trasladar los bienes locados a una distancia mayor de 100 KM de Mar del Plata, a no ser que el locador preste su conformidad por escrito para ese traslado.</div>

  <div class="contrato-clausula"><strong>DUODÉCIMO.</strong> Queda absolutamente prohibido al locatario subalquilar, y/o prestar y/o dar en comando o de cualquier manera desprenderse de la tenencia de los objetos dados en locación. Estos además deberán ser operados por personal técnico o idóneo a criterio del locador.</div>

  <div class="contrato-clausula"><strong>DECIMOCUARTO.</strong> El precio de locación se pagará a los treinta días sin perjuicio de los plazos y recargos por mora, precedentemente previstos.</div>

  <div class="contrato-clausula"><strong>DECIMOSEXTO - JURISDICCIÓN.</strong> Para todos los efectos judiciales y extrajudiciales derivados del presente contrato, el locador constituye domicilio en {html.escape(OWNER_DIRECCION)}, y el locatario en {cliente_direccion}. Ambas partes se someten a la competencia ordinaria de los Tribunales del departamento Judicial de Mar del Plata.</div>

  <div class="contrato-clausula"><strong>DECIMOCTAVO - SEGURO.</strong> El locatario deberá contratar el correspondiente seguro sobre los objetos de locación individualizados, a su exclusivo costo.</div>
</div>

<div class="firmas">
  <div class="firma-box">
    <div style="height: 40px; margin-bottom: 4px;"></div>
    <div class="firma-etiqueta">Firma LOCATARIO</div>
    <div class="firma-etiqueta">Aclaración / DNI</div>
  </div>
  <div class="firma-box">
    <div style="height: 40px; margin-bottom: 4px;"></div>
    <div class="firma-etiqueta">Firma LOCADOR</div>
    <div class="firma-etiqueta">Marín Javier Santini Calarco</div>
  </div>
</div>

<div style="margin-top: 60px; text-align: center; font-size: 9pt; color: #999;">
  Emitido en Mar del Plata, {fecha_hoy}
</div>

<div class="footer">
  Rambla Rental · ramblarental.com.ar
</div>

</div>

</body>
</html>"""


def _packing_list_html(pedido: dict) -> str:
    """Packing list: checklist de salida/retorno, sin precios.

    La vista HTML (?format=html) usa checkboxes reales interactivos con barra
    de progreso. El PDF (Playwright) renderiza los checkboxes como cajas vacías.

    Estructura por ítem:
      - Equipo (principal)
        ↳ Componentes de kit (si aplica)
        ↳ Contenido incluido de la caja (equipo_fichas.contenido_incluido_json)
    """
    fmt_date = _fmt_date_short
    items = pedido.get("items", [])

    rows = ""
    n = 1
    for it in items:
        cant = it.get("cantidad", 1)
        descripcion = html.escape(_nombre_para_pdf(it))
        foto_abs = _abs_image_url(it.get("foto_url"))
        foto_html = (
            f'<img src="{html.escape(foto_abs)}" class="pl-img" alt="foto">'
            if foto_abs
            else '<div class="pl-img pl-img-empty">—</div>'
        )

        rows += f"""
        <tr class="row-main" data-row="{n}">
          <td class="num center">{n}</td>
          <td class="foto-cell">{foto_html}</td>
          <td class="desc">{descripcion}</td>
          <td class="center">{cant}</td>
          <td class="center check-cell"><input type="checkbox" class="chk" data-row="{n}" data-col="s" aria-label="Salida"></td>
          <td class="center check-cell"><input type="checkbox" class="chk" data-row="{n}" data-col="r" aria-label="Retorno"></td>
        </tr>"""
        n += 1

        # Componentes de kit
        for comp in it.get("componentes", []):
            comp_cant = comp.get("cantidad", 1) * cant
            comp_desc = html.escape(_nombre_para_pdf(comp))
            comp_foto_abs = _abs_image_url(comp.get("foto_url"))
            comp_foto = (
                f'<img src="{html.escape(comp_foto_abs)}" class="pl-img pl-img-sm" alt="foto">'
                if comp_foto_abs
                else '<div class="pl-img pl-img-sm pl-img-empty">—</div>'
            )
            rows += f"""
        <tr class="row-sub" data-row="{n}">
          <td class="center" style="color:#bbb;font-size:9pt">↳</td>
          <td class="foto-cell" style="padding-left:16px">{comp_foto}</td>
          <td class="desc sub-desc">Kit: {comp_desc}</td>
          <td class="center">{comp_cant}</td>
          <td class="center check-cell"><input type="checkbox" class="chk" data-row="{n}" data-col="s" aria-label="Salida"></td>
          <td class="center check-cell"><input type="checkbox" class="chk" data-row="{n}" data-col="r" aria-label="Retorno"></td>
        </tr>"""
            n += 1

        # Contenido incluido (de equipo_fichas.contenido_incluido_json)
        contenido_raw = it.get("contenido_incluido_json")
        if contenido_raw:
            try:
                contenido_items = json.loads(contenido_raw)
            except (json.JSONDecodeError, TypeError):
                contenido_items = []
            for ci in contenido_items:
                ci_nombre = html.escape(str(ci.get("nombre") or "—"))
                ci_cant = ci.get("cantidad", 1)
                ci_foto_abs = _abs_image_url(ci.get("foto_url"))
                ci_foto = (
                    f'<img src="{html.escape(ci_foto_abs)}" class="pl-img pl-img-sm" alt="foto">'
                    if ci_foto_abs
                    else '<div class="pl-img pl-img-sm pl-img-empty">—</div>'
                )
                rows += f"""
        <tr class="row-contenido" data-row="{n}">
          <td class="center" style="color:#bbb;font-size:9pt">↳</td>
          <td class="foto-cell" style="padding-left:16px">{ci_foto}</td>
          <td class="desc sub-desc caja-item">&#128230; {ci_nombre}</td>
          <td class="center">{ci_cant}</td>
          <td class="center check-cell"><input type="checkbox" class="chk" data-row="{n}" data-col="s" aria-label="Salida"></td>
          <td class="center check-cell"><input type="checkbox" class="chk" data-row="{n}" data-col="r" aria-label="Retorno"></td>
        </tr>"""
                n += 1

    total_rows = n - 1  # para el contador JS

    if pedido.get("numero_pedido"):
        ref = f"R-{int(pedido['numero_pedido']):04d}"
    else:
        ref = f"#{pedido['id']}"

    fecha_doc = datetime.now().strftime("%d/%m/%Y")

    return f"""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  {_a4_page()}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, 'Helvetica Neue', Arial, sans-serif;
    color: #111; font-size: 11pt; line-height: 1.45;
    margin: 0; padding: 0;
  }}

  /* ── Barra de progreso — solo pantalla ──────────────────── */
  #progress-bar {{
    position: sticky; top: 0; z-index: 10;
    background: #fff; border-bottom: 1px solid #e5e5e5;
    padding: 10px 20px; display: flex; align-items: center; gap: 12px;
    font-size: 10pt;
  }}
  #progress-track {{
    flex: 1; height: 8px; background: #eee; border-radius: 4px; overflow: hidden;
  }}
  #progress-fill {{
    height: 100%; width: 0%; background: #22c55e;
    border-radius: 4px; transition: width .3s ease;
  }}
  #progress-text {{ font-weight: 600; white-space: nowrap; min-width: 90px; text-align: right; }}
  #progress-all-done {{
    display: none; color: #16a34a; font-weight: 700; font-size: 10pt;
  }}
  @media print {{ #progress-bar {{ display: none; }} }}

  /* ── Documento ──────────────────────────────────────────── */
  .doc {{ padding: 20px 24px; max-width: 900px; margin: 0 auto; }}
  @media print {{ .doc {{ padding: 0; }} }}

  .header {{
    display: flex; justify-content: space-between; align-items: flex-start;
    border-bottom: 2px solid #111; padding-bottom: 12px; margin-bottom: 18px;
  }}
  .logo {{
    font-family: 'Helvetica Neue', sans-serif; font-weight: 900; font-size: 22pt;
    letter-spacing: -.5px;
  }}
  .logo em {{ color: #F9B92E; font-style: normal; }}
  .doc-tipo {{ text-align: right; font-size: 10pt; color: #444; }}
  .doc-tipo h1 {{
    font-size: 18pt; font-weight: 800; margin: 0; color: #111;
    text-transform: uppercase; letter-spacing: 1px;
  }}
  .meta {{
    display: grid; grid-template-columns: 1fr 1fr; gap: 14px;
    background: #f6f6f6; padding: 14px 18px; border-radius: 6px; margin-bottom: 16px;
  }}
  .meta-item {{ display: flex; flex-direction: column; gap: 3px; }}
  .meta-label {{
    font-size: 8pt; color: #666; text-transform: uppercase;
    letter-spacing: 1px; font-weight: 700;
  }}
  .meta-val {{ font-size: 11pt; font-weight: 600; }}
  .nota {{
    background: #fffbe6; border-left: 3px solid #F9B92E;
    padding: 10px 14px; font-size: 9.5pt; color: #555; margin-bottom: 16px;
  }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 18px; }}
  th {{
    background: #111; color: #fff; text-align: left;
    padding: 8px 10px; font-size: 9pt; font-weight: 700;
    text-transform: uppercase; letter-spacing: .5px;
  }}
  th.center {{ text-align: center; }}
  td {{
    padding: 7px 10px; border-bottom: 1px solid #e5e5e5; font-size: 10pt;
    vertical-align: middle; transition: background .2s, opacity .2s;
  }}
  td.center {{ text-align: center; }}
  .num {{ width: 28px; color: #999; font-size: 9pt; }}
  .foto-cell {{ width: 44px; padding: 4px 6px; }}
  .pl-img {{
    width: 36px; height: 36px; object-fit: cover;
    border-radius: 3px; background: #f0f0f0; display: block;
  }}
  .pl-img-sm {{ width: 28px; height: 28px; }}
  .pl-img-empty {{
    display: flex; align-items: center; justify-content: center;
    font-size: 10px; color: #bbb;
  }}
  .desc {{ min-width: 200px; }}
  .sub-desc {{ font-size: 9.5pt; color: #555; padding-left: 8px; }}
  .caja-item {{ color: #3b60c4; }}
  .check-cell {{ width: 70px; }}

  /* ── Checkboxes ─────────────────────────────────────────── */
  input[type="checkbox"].chk {{
    width: 22px; height: 22px; cursor: pointer;
    accent-color: #16a34a; border-radius: 4px;
    vertical-align: middle;
  }}
  @media print {{
    /* En PDF los checkboxes se imprimen como cajas vacías/marcadas por el browser */
    input[type="checkbox"].chk {{ width: 18px; height: 18px; cursor: default; }}
  }}

  /* ── Estados de fila ────────────────────────────────────── */
  .row-main {{ background: #fff; }}
  .row-sub {{ background: #fafafa; }}
  .row-contenido {{ background: #f5f8ff; }}

  /* Salida marcada → fondo suave */
  tr.salida-ok td {{ background: #fefce8 !important; }}
  /* Ambos marcados → tachado + verde pálido */
  tr.done td {{ background: #f0fdf4 !important; opacity: .65; }}
  tr.done td.desc, tr.done td.sub-desc {{ text-decoration: line-through; }}

  .firmas {{
    display: grid; grid-template-columns: 1fr 1fr; gap: 40px; margin-top: 40px;
  }}
  .firma {{
    border-top: 1px solid #111; padding-top: 6px; text-align: center;
    font-size: 9pt; color: #555;
  }}
  .footer {{
    margin-top: 18px; text-align: center; font-size: 8pt; color: #999;
    border-top: 1px solid #ddd; padding-top: 6px;
  }}
  @media print {{
    .footer {{
      position: fixed; bottom: 8mm; left: 0; right: 0;
    }}
  }}
</style>
</head>
<body>

<!-- Barra de progreso (solo HTML) -->
<div id="progress-bar">
  <span style="font-size:9.5pt;color:#555">Progreso:</span>
  <div id="progress-track"><div id="progress-fill"></div></div>
  <span id="progress-text">0 / {total_rows}</span>
  <span id="progress-all-done">&#10003; Todo completo</span>
</div>

<div class="doc">

<div class="header">
  <div>
    <div class="logo">Rambla <em>Rental</em></div>
    <div style="font-size:9pt;color:#666;margin-top:4px">Alquiler de equipos audiovisuales</div>
  </div>
  <div class="doc-tipo">
    <h1>Packing List</h1>
    <div style="margin-top:4px">Ref. {ref}</div>
    <div>Emitido: {fecha_doc}</div>
  </div>
</div>

<div class="meta">
  <div class="meta-item">
    <div class="meta-label">Cliente</div>
    <div class="meta-val">{html.escape(pedido.get("cliente_nombre") or "—")}</div>
  </div>
  <div class="meta-item">
    <div class="meta-label">Contacto</div>
    <div class="meta-val" style="font-size:10pt">{html.escape(pedido.get("cliente_email") or pedido.get("cliente_telefono") or "—")}</div>
  </div>
  <div class="meta-item">
    <div class="meta-label">Retiro</div>
    <div class="meta-val">{fmt_date(pedido.get("fecha_desde"))}</div>
  </div>
  <div class="meta-item">
    <div class="meta-label">Devolución prevista</div>
    <div class="meta-val">{fmt_date(pedido.get("fecha_hasta"))}</div>
  </div>
</div>

<div class="nota">
  Tildá cada ítem al entregar (Salida) y al recibir (Retorno).
  Las filas azules (&#128230;) son accesorios de la caja — incluirlos en la entrega.
</div>

<table>
  <thead>
    <tr>
      <th class="center" style="width:28px">#</th>
      <th style="width:44px"></th>
      <th>Equipo / Accesorio</th>
      <th class="center" style="width:50px">Cant.</th>
      <th class="center" style="width:70px">Salida</th>
      <th class="center" style="width:70px">Retorno</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>

<div class="firmas">
  <div class="firma">Firma cliente — aclaración / DNI</div>
  <div class="firma">Firma Rambla Rental</div>
</div>

<div class="footer">
  Rambla Rental · ramblarental.com.ar · Documento generado el {fecha_doc}
</div>

</div><!-- /.doc -->

<script>
(function() {{
  var total = {total_rows};
  var fill  = document.getElementById('progress-fill');
  var text  = document.getElementById('progress-text');
  var done  = document.getElementById('progress-all-done');

  function updateRow(rowId) {{
    var tr = document.querySelector('tr[data-row="' + rowId + '"]');
    if (!tr) return;
    var s = document.querySelector('input.chk[data-row="' + rowId + '"][data-col="s"]');
    var r = document.querySelector('input.chk[data-row="' + rowId + '"][data-col="r"]');
    if (!s || !r) return;
    tr.classList.toggle('salida-ok', s.checked && !r.checked);
    tr.classList.toggle('done',      s.checked && r.checked);
    updateCounter();
  }}

  function updateCounter() {{
    var completados = document.querySelectorAll('tr.done').length;
    var pct = total > 0 ? Math.round(completados / total * 100) : 0;
    fill.style.width = pct + '%';
    text.textContent = completados + ' / ' + total;
    var allDone = completados === total && total > 0;
    done.style.display  = allDone ? 'inline' : 'none';
    text.style.display  = allDone ? 'none'   : 'inline';
    fill.style.background = allDone ? '#16a34a' : '#22c55e';
  }}

  document.querySelectorAll('input.chk').forEach(function(chk) {{
    chk.addEventListener('change', function() {{
      updateRow(this.dataset.row);
    }});
  }});

  updateCounter();
}})();
</script>

</body>
</html>"""


# ── Reporte de liquidación (#88) ──────────────────────────────────────────────
# Espeja el patrón de los documentos de pedido: un builder de HTML branded que
# `_render_pdf` convierte a PDF A4. La data viene del motor `backend/reportes/`
# (vía `liquidar`); acá solo se presenta — no se calcula nada.

def _liquidacion_html(data: dict, titulo: str) -> str:
    """HTML branded del reporte de liquidación para un período (PDF / preview).

    `data` es el dict que devuelve `reportes.liquidacion.liquidar`
    (beneficiarios, por_mes, resumen, por_dueno). `titulo` es el rótulo del
    período (ej. 'junio de 2026')."""
    fmt = lambda n: _fmt_ars(n, zero_dash=False)
    beneficiarios = data.get("beneficiarios", [])
    res = data.get("resumen", {}) or {}
    por_mes = data.get("por_mes", []) or []
    por_dueno = data.get("por_dueno", []) or []
    res_pb = res.get("por_beneficiario", {}) or {}
    fecha_doc = _es_month(datetime.now().strftime("%-d de %B de %Y"))

    # Tarjetas de resumen por beneficiario (lo que le toca a cada uno).
    cards = ""
    for b in beneficiarios:
        cards += f"""
        <div class="card">
          <div class="card-label">{html.escape(str(b))}</div>
          <div class="card-value">{fmt(res_pb.get(b, 0))}</div>
        </div>"""
    cards += f"""
        <div class="card card-total">
          <div class="card-label">Total del período</div>
          <div class="card-value">{fmt(res.get("total", 0))}</div>
        </div>"""

    # Grilla mes × beneficiario (solo si hay más de un mes en el rango).
    grilla = ""
    if len(por_mes) > 1:
        head = "".join(f"<th class='right'>{html.escape(str(b))}</th>" for b in beneficiarios)
        body = ""
        for fila in por_mes:
            pb = fila.get("por_beneficiario", {}) or {}
            celdas = "".join(f"<td class='right'>{fmt(pb.get(b, 0))}</td>" for b in beneficiarios)
            body += (
                f"<tr><td>{html.escape(_es_month(str(fila.get('mes', ''))))}</td>"
                f"{celdas}<td class='right strong'>{fmt(fila.get('total', 0))}</td></tr>"
            )
        tot = "".join(f"<td class='right'>{fmt(res_pb.get(b, 0))}</td>" for b in beneficiarios)
        grilla = f"""
        <h2>Por mes</h2>
        <table class="grid">
          <thead><tr><th>Mes</th>{head}<th class="right">Total</th></tr></thead>
          <tbody>{body}</tbody>
          <tfoot><tr><td class="strong">TOTAL</td>{tot}<td class="right strong">{fmt(res.get('total', 0))}</td></tr></tfoot>
        </table>"""

    # Detalle por dueño: equipos + cuánto generó cada uno.
    detalle = ""
    for d in por_dueno:
        filas = ""
        for eq in d.get("equipos", []):
            veces = eq.get("veces")
            veces_txt = f"{veces}" if veces not in (None, "") else "—"
            filas += (
                f"<tr><td>{html.escape(str(eq.get('equipo', '')))}</td>"
                f"<td class='center'>{veces_txt}</td>"
                f"<td class='right'>{fmt(eq.get('monto', 0))}</td></tr>"
            )
        detalle += f"""
        <div class="dueno">
          <div class="dueno-head">
            <span class="dueno-name">{html.escape(str(d.get("dueno", "")))}</span>
            <span class="dueno-tot">{fmt(d.get("monto_generado", 0))}
              <span class="dueno-sub">· {d.get("pedidos", 0)} alquileres</span></span>
          </div>
          <table class="detail">
            <thead><tr><th>Equipo</th><th class="center">Veces</th><th class="right">Generado</th></tr></thead>
            <tbody>{filas or '<tr><td colspan="3" class="empty">Sin equipos con ingreso en el período.</td></tr>'}</tbody>
          </table>
        </div>"""

    if not por_dueno:
        detalle = '<p class="empty">No hay pedidos saldados en este período.</p>'

    return f"""<!DOCTYPE html>
<html lang="es"><head>
<meta charset="utf-8">
<title>Liquidación — {html.escape(titulo)}</title>
<style>
  {_a4_page(margin="0")}
  * {{ box-sizing: border-box; }}
  html {{ background: #f1efe9; }}
  body {{ font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
          color: #2a251e; margin: 0; padding: 0; font-size: 13px; }}
  /* La hoja A4: en pantalla (preview) se ve como una página centrada; en el
     PDF llena la hoja A4 con el padding como margen. */
  .sheet {{ width: 210mm; min-height: 297mm; margin: 16px auto; padding: 16mm 15mm;
            background: #fff; box-shadow: 0 1px 10px rgba(0,0,0,.12); box-sizing: border-box; }}
  @media print {{
    html {{ background: #fff; }}
    .sheet {{ width: auto; min-height: 0; margin: 0; box-shadow: none; }}
  }}
  .head {{ display: flex; justify-content: space-between; align-items: flex-end;
           border-bottom: 3px solid #FAB428; padding-bottom: 14px; margin-bottom: 22px; }}
  .head h1 {{ font-size: 22px; margin: 0; }}
  .head .sub {{ color: #8a8378; font-size: 12px; margin-top: 4px; }}
  .head .brand {{ text-align: right; font-size: 12px; color: #6b6457; }}
  .head .brand strong {{ display: block; color: #2a251e; font-size: 15px; }}
  h2 {{ font-size: 14px; margin: 24px 0 10px; color: #2a251e; }}
  .cards {{ display: flex; flex-wrap: wrap; gap: 10px; }}
  .card {{ flex: 1 1 140px; border: 1px solid #e5e1d8; border-radius: 10px; padding: 12px 14px; }}
  .card-label {{ font-size: 11px; color: #8a8378; text-transform: uppercase; letter-spacing: .04em; }}
  .card-value {{ font-size: 19px; font-weight: 700; margin-top: 4px; }}
  .card-total {{ background: #2a251e; border-color: #2a251e; }}
  .card-total .card-label {{ color: #d8d2c6; }}
  .card-total .card-value {{ color: #fff; }}
  table {{ width: 100%; border-collapse: collapse; }}
  .grid th, .grid td {{ padding: 7px 9px; border-bottom: 1px solid #eee; }}
  .grid thead th {{ background: #faf8f3; font-size: 11px; text-transform: uppercase;
                    letter-spacing: .03em; color: #6b6457; }}
  .grid tfoot td {{ border-top: 2px solid #d8d2c6; font-weight: 700; }}
  .dueno {{ border: 1px solid #e5e1d8; border-radius: 10px; margin-bottom: 12px;
            overflow: hidden; page-break-inside: avoid; }}
  .dueno-head {{ display: flex; justify-content: space-between; align-items: baseline;
                 background: #faf8f3; padding: 10px 14px; border-bottom: 1px solid #e5e1d8; }}
  .dueno-name {{ font-weight: 700; font-size: 14px; }}
  .dueno-tot {{ font-weight: 700; font-size: 14px; }}
  .dueno-sub {{ font-weight: 400; font-size: 11px; color: #8a8378; }}
  .detail th, .detail td {{ padding: 6px 14px; border-bottom: 1px solid #f0ede6; font-size: 12px; }}
  .detail thead th {{ font-size: 10px; text-transform: uppercase; color: #8a8378; text-align: left; }}
  .right {{ text-align: right; }}
  .center {{ text-align: center; }}
  .strong {{ font-weight: 700; }}
  .empty {{ color: #8a8378; font-style: italic; padding: 10px 14px; }}
  .foot {{ margin-top: 26px; padding-top: 12px; border-top: 1px solid #e5e1d8;
           font-size: 11px; color: #8a8378; text-align: center; }}
</style>
</head>
<body>
  <div class="sheet">
    <div class="head">
      <div>
        <h1>Liquidación</h1>
        <div class="sub">{html.escape(titulo)} · ingreso 100% pagado, repartido</div>
      </div>
      <div class="brand">
        <strong>Rambla Rental</strong>
        Reporte generado el {fecha_doc}
      </div>
    </div>

    <div class="cards">{cards}</div>
    {grilla}
    <h2>Detalle por dueño</h2>
    {detalle}

    <div class="foot">
      Rambla Rental · alquiler de equipos audiovisuales · reporte interno de liquidación
    </div>
  </div>
</body>
</html>"""
