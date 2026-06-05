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

# Documentos de pedido (rediseño DS v1): los 4 builders
# (presupuesto/albarán/contrato/packing) viven en `pdf_templates.py` (port
# drop-in del handoff de Claude Design). Se re-exportan acá para no romper los
# imports existentes (`from pdf import _pedido_html, ...` en routes/tests).
# El 5º documento (`_liquidacion_html`, reporte) sigue acá — no entró al rediseño.
from pdf_templates import (  # noqa: F401
    _pedido_html,
    _albaran_html,
    _contrato_html,
    _packing_list_html,
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
    """Parsea un valor de reposición a entero (pesos).

    El valor llega de la BD como número (la columna `valor_reposicion` es
    FLOAT, en pesos) → se redondea directo. Borrarle el '.' a un float
    (ej. 500.0 → '5000') lo multiplicaba por 10 — ese era el bug.
    Solo cuando llega un string con formato argentino ('$1.500') se limpian
    los separadores: ahí el '.' es separador de miles, no decimal.
    """
    if v is None or v == "":
        return 0
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        try:
            return int(round(v))
        except Exception:
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
  body {{ font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
          color: #2a251e; margin: 0; padding: 0; font-size: 13px; }}
  /* La hoja: en el PDF es A4 (llena la hoja, el padding hace de margen). En
     pantalla (preview del modal) se adapta al ancho del iframe para verse
     completa — Chromium rasteriza el PDF con media `print`, así que el override
     `screen` no afecta al PDF. */
  .sheet {{ width: 210mm; min-height: 297mm; margin: 0 auto; padding: 16mm 15mm;
            background: #fff; box-sizing: border-box; }}
  @media screen {{
    html {{ background: #f1efe9; }}
    .sheet {{ width: 100%; min-height: 0; margin: 0; padding: 28px 30px; }}
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
