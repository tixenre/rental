"""
pdf.py — Generación de PDFs con Playwright.
Contiene los templates HTML y el renderer compartido.
"""

import asyncio
import html
import os
import re
from datetime import datetime


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
    _a4_page,
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


# Etiqueta legible de cada tipo de documento para el NOMBRE del archivo. Va
# entre el número de pedido y el nombre del cliente para que, en la vista de
# adjuntos, se distingan de un vistazo (R-0405_Albaran_..., R-0405_Contrato_...).
_DOC_LABELS = {
    "presupuesto": "Remito",
    "albaran": "Detalle-de-seguro",
    "contrato": "Contrato",
    "packing-list": "Checklist-de-retiro",
}


def _pedido_filename(pedido: dict, doc: str = "presupuesto") -> str:
    """Devuelve algo como 'R-0001_Albaran_Martinez-Santiago.pdf': número de
    pedido, tipo de documento y cliente, en ese orden."""
    if pedido.get("numero_pedido"):
        num = f"R-{int(pedido['numero_pedido']):04d}"
    else:
        num = str(pedido["id"])
    cliente = _slug(pedido.get("cliente_nombre") or "")
    doc_label = _DOC_LABELS.get(doc, _DOC_LABELS["presupuesto"])
    return f"{num}_{doc_label}_{cliente}.pdf"


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


async def _render_pdf(html: str, *, page_size: tuple[int, int | None] | None = None) -> bytes:
    """Renderiza un HTML como PDF usando Playwright.

    Reutiliza un único proceso Chromium; abre y cierra una page por request.
    Por default exporta A4 (documentos de pedido/reportes). `page_size`
    (width_px, height_px) fuerza un tamaño de página propio en vez de A4 —
    para piezas que no son A4 (p.ej. la factura "celular", pensada para
    compartir por WhatsApp). `height_px=None` mide el alto real del
    contenido (`document.body.scrollHeight`) para que la página termine
    justo donde termina el comprobante, sin cortar ni dejar espacio de más.
    """
    browser   = await _get_browser()
    page      = await browser.new_page()
    try:
        await page.set_content(html, wait_until="networkidle")
        margin = {"top": "0", "bottom": "0", "left": "0", "right": "0"}
        if page_size:
            width_px, height_px = page_size
            if height_px is None:
                height_px = await page.evaluate("document.body.scrollHeight")
            pdf_bytes = await page.pdf(
                width=f"{width_px}px", height=f"{height_px}px",
                margin=margin, print_background=True,
            )
        else:
            pdf_bytes = await page.pdf(format="A4", margin=margin, print_background=True)
    finally:
        await page.close()
    return pdf_bytes


async def _render_imagen(
    html: str, *, page_size: tuple[int, int | None] | None = None, formato: str = "png"
) -> bytes:
    """Screenshot del HTML (Playwright `page.screenshot`) — misma infraestructura que
    `_render_pdf` (mismo browser compartido), para compartir un layout como imagen en vez de PDF
    (ej. el layout "celular" de una factura, pensado para WhatsApp — una imagen se ve inline en el
    chat, un PDF aparece como ícono de archivo). Disponible para cualquier layout, no solo
    "celular": mismo contrato de `page_size` que `_render_pdf` — sin especificar, usa el ancho A4
    (794px) con el alto real del contenido; con `page_size` (width_px, height_px|None), fuerza ese
    tamaño (celular: 4:5 fijo). `formato`: "png" (default, sin pérdida) o "jpeg".

    Es un artefacto de nivel "compartir rápido" (como el preview HTML) — no pasa por
    `arca_fe.asegurar_pdf` (esa firma es específica de PDF), no reemplaza al documento
    certificado."""
    browser = await _get_browser()
    page = await browser.new_page()
    try:
        await page.set_content(html, wait_until="networkidle")
        if page_size:
            width_px, height_px = page_size
            if height_px is None:
                height_px = await page.evaluate("document.body.scrollHeight")
        else:
            width_px = 794
            height_px = await page.evaluate("document.body.scrollHeight") or 1123
        await page.set_viewport_size({"width": width_px, "height": height_px})
        img_bytes = await page.screenshot(type=formato)
    finally:
        await page.close()
    return img_bytes


# ── Reporte de liquidación (#88) ──────────────────────────────────────────────
# Espeja el patrón de los documentos de pedido: un builder de HTML branded que
# `_render_pdf` convierte a PDF A4. La data de liquidación viene del motor
# `backend/reportes/` (vía `liquidar`); las stats del 'Resumen general' vienen de
# `routes.estadisticas.compute_estadisticas`. Acá solo se presenta — no se calcula
# nada de negocio (solo derivaciones de presentación: %, promedios, abreviaturas).
#
# Diseño en el Design System v1 (mismo shell branded que presupuesto/albarán/…):
# reusa `_fonts_css()`, `WORDMARK` y los tokens del DS de `pdf_templates`. Todos
# los colores salen de tokens; los acentos de estado (verde/azul/rosa) salen de la
# paleta oficial `_ESTADOS`.

from pdf_templates import (  # noqa: E402
    _fonts_css as _ds_fonts_css,
    _active_wordmark as _ds_active_wordmark,
    _DOC_CSS as _DS_DOC_CSS,
    _footer as _ds_footer,
    _ESTADOS as _DS_ESTADOS,
)

# Acentos de estado del DS (color sólido), por nombre — fuente única `_ESTADOS`.
_REP_VERDE = _DS_ESTADOS["confirmado"][0]   # #009971
_REP_AZUL = _DS_ESTADOS["presupuesto"][0]   # #1097DB
_REP_ROSA = _DS_ESTADOS["devuelto"][0]      # #ED7BAD
_REP_DESTRUCTIVE = _DS_ESTADOS["cancelado"][0]

_MESES_ABBR = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN",
               "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]
_MESES_LARGO = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
                "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _rep_mes_abbr(ym: str) -> str:
    """'2026-06' → 'JUN'. Robusto ante formatos inesperados."""
    try:
        return _MESES_ABBR[int(str(ym).split("-")[1]) - 1]
    except (IndexError, ValueError):
        return html.escape(str(ym or ""))[:3].upper()


def _rep_mes_eyebrow(ym: str) -> str:
    """'2026-06' → 'JUNIO 2026' (eyebrow del período)."""
    try:
        y, m = str(ym).split("-")[:2]
        return f"{_MESES_LARGO[int(m) - 1].upper()} {y}"
    except (IndexError, ValueError):
        return html.escape(str(ym or "")).upper()


def _rep_mes_largo(ym: str) -> str:
    """'2026-06' → 'junio de 2026'."""
    try:
        y, m = str(ym).split("-")[:2]
        return f"{_MESES_LARGO[int(m) - 1]} de {y}"
    except (IndexError, ValueError):
        return html.escape(str(ym or ""))


def _rep_fmt_compact(n) -> str:
    """Monto compacto para etiquetas de barras: '$ 1.250k' / '$ 980'."""
    try:
        v = int(float(n or 0))
    except (TypeError, ValueError):
        return "$ 0"
    if abs(v) >= 1000:
        return "$ " + f"{round(v / 1000):,}".replace(",", ".") + "k"
    return "$ " + f"{v:,}".replace(",", ".")


def _liquidacion_html(data: dict, titulo: str, stats: dict | None = None) -> str:
    """HTML branded (Design System) del reporte 'Reportes' para un período.

    `data` es el dict de `reportes.liquidacion.liquidar` (beneficiarios, resumen,
    por_dueno). `titulo` es el rótulo del período (ej. 'junio de 2026'). `stats`
    es el dict de `routes.estadisticas.compute_estadisticas`; si es None, solo se
    rinde la sección Liquidación (compat hacia atrás)."""
    fmt = lambda n: _fmt_ars(n, zero_dash=False)
    esc = lambda s: html.escape(str(s if s is not None else ""))

    beneficiarios = data.get("beneficiarios", []) or []
    res = data.get("resumen", {}) or {}
    por_dueno = data.get("por_dueno", []) or []
    res_pb = res.get("por_beneficiario", {}) or {}
    total_periodo = res.get("total", 0)

    fecha_doc = _es_month(datetime.now().strftime("%-d de %B de %Y"))

    # Eyebrow del período de liquidación: derivado del `mes` del dict si está, si
    # no del propio título.
    mes_liq = data.get("mes")
    periodo_eyebrow = _rep_mes_eyebrow(mes_liq) if mes_liq else esc(titulo).upper()

    # ── HEADER (barra amber full-bleed: wordmark blanco izq · info der) ───────
    header = (
        '<header class="rep-header"><div class="rep-header-top">'
        f'<div class="rep-brand"><span class="rep-wordmark">{_ds_active_wordmark()}</span></div>'
        '<div class="rep-head-meta">'
        '<div class="rep-eyebrow">Reporte interno</div>'
        '<h1 class="rep-title">Reportes</h1>'
        '<div class="rep-eyebrow">Mensual</div>'
        f'<div class="rep-head-date">Generado {esc(fecha_doc)}</div>'
        '</div></div></header>'
    )

    # ═══ SECCIÓN LIQUIDACIÓN ═════════════════════════════════════════════════
    # Cards "A cobrar por beneficiario".
    benef_cards = ""
    for b in beneficiarios:
        benef_cards += (
            '<div class="rep-card rep-card--benef">'
            f'<div class="rep-card-label">{esc(b)}</div>'
            f'<div class="rep-card-value">{fmt(res_pb.get(b, 0))}</div></div>'
        )
    benef_cards += (
        '<div class="rep-card rep-card--total">'
        '<div class="rep-card-label">Total del período</div>'
        f'<div class="rep-card-value">{fmt(total_periodo)}</div></div>'
    )

    # Detalle por dueño.
    detalle = ""
    for d in por_dueno:
        gen = d.get("monto_generado", 0) or 0
        filas = ""
        for eq in d.get("equipos", []):
            veces = eq.get("veces")
            veces_txt = f"{veces}" if veces not in (None, "") else "—"
            filas += (
                f'<tr><td>{esc(eq.get("equipo", ""))}</td>'
                f'<td class="c mono">{veces_txt}</td>'
                f'<td class="r mono">{fmt(eq.get("monto", 0))}</td></tr>'
            )
        if not filas:
            filas = ('<tr><td colspan="3" class="rep-empty-cell">'
                     'Sin equipos con ingreso en el período.</td></tr>')

        # Pedidos/rentals (2026-07-04): mismo total, visto por pedido en vez de
        # por equipo — # de pedido, cliente, fecha de saldado, monto.
        filas_pedidos = ""
        for p in d.get("pedidos_detalle", []):
            filas_pedidos += (
                f'<tr><td class="mono">#{esc(p.get("numero_pedido", ""))}</td>'
                f'<td>{esc(p.get("cliente", "") or "—")}</td>'
                f'<td class="c mono">{esc(_fmt_date_short(p.get("fecha")))}</td>'
                f'<td class="r mono">{fmt(p.get("monto", 0))}</td></tr>'
            )
        if not filas_pedidos:
            filas_pedidos = ('<tr><td colspan="4" class="rep-empty-cell">'
                              'Sin pedidos con ingreso en el período.</td></tr>')

        reparto = d.get("reparto", {}) or {}
        chips = []
        for b, m in reparto.items():
            pct = round((m / gen) * 100) if gen else 0
            chips.append(f"{esc(b)} {pct}%")
        reparto_html = ""
        if chips:
            reparto_html = (
                '<div class="rep-dueno-foot"><span class="rep-reparte-lbl">Reparte</span>'
                f'{" · ".join(chips)}</div>'
            )

        detalle += (
            '<div class="rep-dueno">'
            '<div class="rep-dueno-head"><span class="rep-dot"></span>'
            f'<span class="rep-dueno-name">{esc(d.get("dueno", ""))}</span>'
            '<span class="rep-dueno-tot">'
            f'{fmt(gen)} <span class="rep-dueno-sub">· {d.get("pedidos", 0)} alquileres</span>'
            '</span></div>'
            '<table class="rep-tbl"><thead><tr>'
            '<th>Equipo</th><th class="c">Veces</th><th class="r">Generado</th>'
            f'</tr></thead><tbody>{filas}</tbody></table>'
            '<table class="rep-tbl rep-tbl--pedidos"><thead><tr>'
            '<th>Pedido</th><th>Cliente</th><th class="c">Fecha</th><th class="r">Monto</th>'
            f'</tr></thead><tbody>{filas_pedidos}</tbody></table>'
            f'{reparto_html}</div>'
        )
    if not por_dueno:
        detalle = '<p class="rep-empty">No hay pedidos saldados en este período.</p>'

    seccion_liq = (
        '<section class="rep-section">'
        '<div class="rep-sec-head"><h2 class="rep-h2">Liquidación</h2>'
        f'<span class="rep-sec-eyebrow">{periodo_eyebrow}</span></div>'
        '<p class="rep-sub">Pedidos 100% pagados, atribuidos al día de pago y '
        'repartidos por dueño.</p>'
        '<div class="rep-h3-row"><h3 class="rep-h3">A cobrar por beneficiario</h3>'
        f'<span class="rep-h3-meta">total · {fmt(total_periodo)}</span></div>'
        f'<div class="rep-cards">{benef_cards}</div>'
        '<div class="rep-h3-row"><h3 class="rep-h3">Detalle por dueño</h3>'
        f'<span class="rep-h3-meta">generado · {fmt(total_periodo)}</span></div>'
        f'{detalle}</section>'
    )

    # ═══ SECCIÓN RESUMEN GENERAL (opcional) ══════════════════════════════════
    # Se rinde si `stats` no es None (un dict vacío → estados vacíos, no se omite).
    seccion_stats = _resumen_general_html(stats) if stats is not None else ""

    body = header + seccion_liq + seccion_stats + _ds_footer()

    head = (
        '<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">'
        f'<title>Reportes — {esc(titulo)}</title>'
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">'
        + _ds_fonts_css()
        + "<style>" + _DS_DOC_CSS + _REP_CSS + "</style></head><body>"
    )
    return head + '<article class="paper">' + body + "</article></body></html>"


def _resumen_general_html(stats: dict) -> str:
    """Sección 'Resumen general' del reporte (contexto histórico). Recibe el dict
    de `compute_estadisticas`. Robusto ante claves vacías."""
    esc = lambda s: html.escape(str(s if s is not None else ""))
    fmt = lambda n: _fmt_ars(n, zero_dash=False)

    totales = stats.get("totales", {}) or {}
    por_mes = stats.get("por_mes", []) or []
    crecimiento = stats.get("crecimiento", []) or []
    por_dueno = stats.get("por_dueno", []) or []
    top_clientes = stats.get("top_clientes", []) or []

    total_ars = totales.get("total_ars") or 0
    total_pedidos = totales.get("total_pedidos") or 0
    total_clientes = totales.get("total_clientes") or 0

    # Eyebrow del período: último mes con datos (por_mes viene DESC) o 'histórico'.
    if por_mes:
        ultimo_mes = por_mes[0].get("mes")
        periodo_eyebrow = _rep_mes_eyebrow(ultimo_mes)
    else:
        periodo_eyebrow = "HISTÓRICO"

    # ── 4 cards ──────────────────────────────────────────────────────────────
    promedio = (total_ars / total_pedidos) if total_pedidos else 0
    ratio = round(total_pedidos / total_clientes, 1) if total_clientes else 0

    # Crecimiento del último mes (crecimiento viene DESC por mes).
    crec_pct, crec_prev = 0, None
    if crecimiento:
        crec_pct = crecimiento[0].get("crecimiento_pct") or 0
        if len(crecimiento) > 1:
            crec_prev = crecimiento[1].get("mes")
    if crec_pct > 0:
        crec_color, crec_txt = _REP_VERDE, f"+{crec_pct:g}%"
    elif crec_pct < 0:
        crec_color, crec_txt = _REP_DESTRUCTIVE, f"{crec_pct:g}%"
    else:
        crec_color, crec_txt = "var(--muted)", f"{crec_pct:g}%"
    crec_sub = f"vs {_rep_mes_largo(crec_prev)}" if crec_prev else "sin mes previo"

    cards = (
        '<div class="rep-stat-card"><div class="rep-stat-label">Facturado neto</div>'
        f'<div class="rep-stat-num">{fmt(total_ars)}</div>'
        '<div class="rep-stat-sub">ingreso finalizado</div></div>'
        '<div class="rep-stat-card"><div class="rep-stat-label">Pedidos</div>'
        f'<div class="rep-stat-num">{total_pedidos}</div>'
        f'<div class="rep-stat-sub">{fmt(promedio)} promedio</div></div>'
        '<div class="rep-stat-card"><div class="rep-stat-label">Clientes</div>'
        f'<div class="rep-stat-num">{total_clientes}</div>'
        f'<div class="rep-stat-sub">{ratio:g} pedidos c/u</div></div>'
        '<div class="rep-stat-card"><div class="rep-stat-label">Crecimiento</div>'
        f'<div class="rep-stat-num" style="color:{crec_color}">{crec_txt}</div>'
        f'<div class="rep-stat-sub">{crec_sub}</div></div>'
    )

    # ── Ingresos por dueño (barras) ──────────────────────────────────────────
    suma_dueno = sum((d.get("total_ars") or 0) for d in por_dueno)
    # Paleta de barras: Rambla = amber; los demás siguen el orden del DS.
    paleta = [_REP_AZUL, _REP_ROSA, _REP_VERDE, _REP_DESTRUCTIVE]
    pal_i = 0
    barras = ""
    for d in por_dueno:
        dueno = d.get("dueno", "")
        monto = d.get("total_ars") or 0
        pct = (monto / suma_dueno * 100) if suma_dueno else 0
        if str(dueno).strip().lower() == "rambla":
            color = "var(--amber)"
        else:
            color = paleta[pal_i % len(paleta)]
            pal_i += 1
        items = d.get("items") or 0
        barras += (
            '<div class="rep-bar-row">'
            '<div class="rep-bar-top"><span class="rep-bar-name">'
            f'<span class="rep-dot" style="background:{color}"></span>{esc(dueno)}</span>'
            f'<span class="rep-bar-val mono">{fmt(monto)} '
            f'<span class="rep-bar-pct">{round(pct)}%</span></span></div>'
            '<div class="rep-bar-track">'
            f'<div class="rep-bar-fill" style="width:{max(pct, 1.5):.1f}%;background:{color}"></div></div>'
            f'<div class="rep-bar-foot">{items} items</div></div>'
        )
    if not por_dueno:
        barras = '<p class="rep-empty">Sin ingresos por dueño en el histórico.</p>'

    # ── Clientes del mes (top 5) ─────────────────────────────────────────────
    top = top_clientes[:5]
    filas_cli = ""
    for i, c in enumerate(top, 1):
        filas_cli += (
            f'<tr><td class="c mono rep-rank">{i}</td>'
            f'<td>{esc(c.get("cliente", "—"))}</td>'
            f'<td class="c mono">{c.get("pedidos", 0)}</td>'
            f'<td class="r mono">{fmt(c.get("total_ars", 0))}</td></tr>'
        )
    if not filas_cli:
        filas_cli = '<tr><td colspan="4" class="rep-empty-cell">Sin clientes en el histórico.</td></tr>'
    clientes_tbl = (
        '<table class="rep-tbl rep-cli-tbl"><thead><tr>'
        '<th class="c">#</th><th>Cliente</th><th class="c">Pedidos</th>'
        '<th class="r">Facturado</th></tr></thead>'
        f'<tbody>{filas_cli}</tbody></table>'
    )

    # ── Tendencia · barras de los últimos 6 meses ────────────────────────────
    # por_mes viene DESC → tomamos los 6 más recientes y los damos vuelta a ASC.
    meses6 = list(reversed(por_mes[:6]))
    max_total = max((m.get("total_ars") or 0) for m in meses6) if meses6 else 0
    chart_bars = ""
    for i, m in enumerate(meses6):
        t = m.get("total_ars") or 0
        h = (t / max_total * 100) if max_total else 0
        ultima = (i == len(meses6) - 1)
        color = "var(--amber)" if ultima else "var(--hairline-bar)"
        chart_bars += (
            '<div class="rep-chart-col">'
            f'<div class="rep-chart-amt mono">{_rep_fmt_compact(t)}</div>'
            '<div class="rep-chart-barwrap">'
            f'<div class="rep-chart-bar" style="height:{max(h, 2):.1f}%;background:{color}"></div></div>'
            f'<div class="rep-chart-lbl">{_rep_mes_abbr(m.get("mes"))}</div></div>'
        )
    if not meses6:
        chart_bars = '<p class="rep-empty">Sin histórico mensual.</p>'

    n_meses = len(meses6)
    n_top = len(top)

    return (
        '<section class="rep-section rep-section--stats">'
        '<div class="rep-sec-head"><h2 class="rep-h2">Resumen general</h2>'
        f'<span class="rep-sec-eyebrow">{periodo_eyebrow}</span></div>'
        '<p class="rep-sub">Contexto · histórico de pedidos finalizados.</p>'
        f'<div class="rep-stat-grid">{cards}</div>'
        '<div class="rep-h3-row"><h3 class="rep-h3">Ingresos por dueño</h3>'
        f'<span class="rep-h3-meta">neto · {fmt(suma_dueno)}</span></div>'
        f'<div class="rep-bars">{barras}</div>'
        '<div class="rep-h3-row"><h3 class="rep-h3">Clientes del mes</h3>'
        f'<span class="rep-h3-meta">top {n_top}</span></div>'
        f'{clientes_tbl}'
        '<div class="rep-h3-row"><h3 class="rep-h3">'
        f'Tendencia · {n_meses} meses</h3>'
        '<span class="rep-h3-meta">neto mensual</span></div>'
        f'<div class="rep-chart">{chart_bars}</div>'
        '</section>'
    )


# CSS específico de Reportes — se concatena después de `_DS_DOC_CSS`, así que
# hereda todos los tokens del DS (--amber/--ink/--surface/--hairline/--muted/…).
_REP_CSS = r"""
:root{ --hairline-bar:oklch(0.85 0.01 80); }

/* Header (barra amber full-bleed: wordmark blanco izq · info doc der).
   Margen negativo = sangra al borde de la hoja (contrarresta @page margin:14mm). */
.rep-header{margin:0 -14mm 26px;padding:34px 14mm 20px;background:var(--amber);
  -webkit-print-color-adjust:exact;print-color-adjust:exact}
.rep-header-top{display:flex;justify-content:space-between;align-items:center;gap:28px}
.rep-brand{display:flex;flex-direction:column;gap:8px}
.rep-wordmark{color:#fff}
.rep-wordmark svg{height:38px!important}
.rep-head-meta{display:flex;flex-direction:column;align-items:flex-end;text-align:right;gap:2px}
.rep-eyebrow{font-family:var(--font-mono);font-size:9.5px;letter-spacing:.22em;
  text-transform:uppercase;color:color-mix(in oklch,var(--ink) 64%,var(--amber));white-space:nowrap}
.rep-head-date{font-family:var(--font-mono);font-size:10.5px;
  color:color-mix(in oklch,var(--ink) 64%,var(--amber));white-space:nowrap}
.rep-title{font-family:var(--font-sans);font-weight:700;font-size:30px;letter-spacing:-.015em;
  line-height:1;margin:3px 0;color:var(--ink)}

/* Section */
.rep-section{margin-top:6px}
.rep-section--stats{margin-top:30px;padding-top:26px;border-top:1px solid var(--hairline)}
.rep-sec-head{display:flex;justify-content:space-between;align-items:baseline;gap:14px;margin-bottom:4px}
.rep-h2{font-family:var(--font-sans);font-weight:700;font-size:21px;letter-spacing:-.01em}
.rep-sec-eyebrow{font-family:var(--font-mono);font-size:11px;font-weight:600;letter-spacing:.16em;
  text-transform:uppercase;color:color-mix(in oklch,var(--amber) 78%,var(--ink));white-space:nowrap}
.rep-sub{font-size:12px;color:var(--muted);line-height:1.5;margin-bottom:14px}

/* H3 row (título + meta mono a la derecha) */
.rep-h3-row{display:flex;justify-content:space-between;align-items:baseline;gap:14px;
  margin:24px 0 12px}
.rep-h3{font-family:var(--font-sans);font-weight:600;font-size:14px}
.rep-h3-meta{font-family:var(--font-mono);font-size:10.5px;color:var(--muted);
  letter-spacing:.04em;white-space:nowrap}

/* Cards de beneficiario */
.rep-cards{display:flex;flex-wrap:wrap;gap:10px}
.rep-card{flex:1 1 150px;border:1px solid var(--hairline);border-radius:var(--r-md);
  padding:13px 15px;background:var(--surface)}
.rep-card-label{font-family:var(--font-mono);font-size:9px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--muted)}
.rep-card-value{font-family:var(--font-mono);font-variant-numeric:tabular-nums;
  font-weight:600;font-size:20px;margin-top:6px}
.rep-card--total{background:var(--amber);border-color:var(--amber);
  -webkit-print-color-adjust:exact;print-color-adjust:exact}
.rep-card--total .rep-card-label{color:color-mix(in oklch,var(--ink) 70%,transparent)}
.rep-card--total .rep-card-value{color:var(--ink)}

/* Card de dueño */
.rep-dueno{border:1px solid var(--hairline);border-radius:var(--r-lg);
  background:var(--surface);margin-bottom:12px;overflow:hidden;break-inside:avoid}
.rep-dueno-head{display:flex;align-items:baseline;gap:9px;padding:12px 16px;
  border-bottom:1px solid var(--hairline)}
.rep-dot{width:8px;height:8px;border-radius:50%;background:var(--amber);flex-shrink:0;
  align-self:center;-webkit-print-color-adjust:exact;print-color-adjust:exact}
.rep-dueno-name{font-weight:600;font-size:14px}
.rep-dueno-tot{margin-left:auto;font-family:var(--font-mono);font-variant-numeric:tabular-nums;
  font-weight:600;font-size:14px;white-space:nowrap}
.rep-dueno-sub{font-weight:400;font-size:10.5px;color:var(--muted)}
.rep-dueno-foot{padding:10px 16px;border-top:1px solid var(--hairline);
  font-family:var(--font-mono);font-size:10px;letter-spacing:.04em;color:var(--muted)}
.rep-reparte-lbl{font-weight:700;letter-spacing:.14em;text-transform:uppercase;
  color:color-mix(in oklch,var(--amber) 72%,var(--ink));margin-right:8px}

/* Tabla genérica del reporte */
.rep-tbl{width:100%;border-collapse:collapse}
.rep-tbl thead th{font-family:var(--font-mono);font-size:8.5px;font-weight:600;
  letter-spacing:.12em;text-transform:uppercase;color:var(--muted);text-align:left;
  padding:0 16px 8px}
.rep-tbl th.r,.rep-tbl td.r{text-align:right}
.rep-tbl th.c,.rep-tbl td.c{text-align:center}
.rep-tbl tbody td{padding:8px 16px;border-top:1px solid var(--hairline);font-size:12px;
  vertical-align:middle}
.rep-tbl .mono{font-family:var(--font-mono);font-variant-numeric:tabular-nums}
.rep-tbl td.r,.rep-tbl td.c{white-space:nowrap}
.rep-dueno .rep-tbl thead th{padding-top:10px}
.rep-tbl--pedidos{margin-top:4px}
.rep-tbl--pedidos thead th{border-top:1px solid var(--hairline);padding-top:14px}
.rep-cli-tbl{border:1px solid var(--hairline);border-radius:var(--r-lg);overflow:hidden}
.rep-cli-tbl thead th{padding:10px 16px 8px;background:var(--surface)}
.rep-rank{color:var(--muted)}
.rep-empty-cell{color:var(--muted);font-style:italic;text-align:center;padding:14px}
.rep-empty{color:var(--muted);font-style:italic;font-size:12px;padding:8px 0}

/* Stats: 4 cards grandes */
.rep-stat-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.rep-stat-card{border:1px solid var(--hairline);border-radius:var(--r-md);
  background:var(--surface);padding:14px 16px}
.rep-stat-label{font-family:var(--font-mono);font-size:8.5px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--muted)}
.rep-stat-num{font-family:"Champ Black",var(--font-sans);font-weight:900;font-size:23px;
  letter-spacing:-.01em;line-height:1.1;margin-top:8px;font-variant-numeric:tabular-nums}
.rep-stat-sub{font-family:var(--font-mono);font-size:9.5px;color:var(--muted);margin-top:6px}

/* Stats: barras de ingresos por dueño */
.rep-bars{display:flex;flex-direction:column;gap:14px}
.rep-bar-top{display:flex;justify-content:space-between;align-items:baseline;gap:12px}
.rep-bar-name{display:flex;align-items:center;gap:8px;font-weight:600;font-size:13px}
.rep-bar-val{font-family:var(--font-mono);font-variant-numeric:tabular-nums;font-size:12px;
  font-weight:600;white-space:nowrap}
.rep-bar-pct{color:var(--muted);font-weight:400;margin-left:4px}
.rep-bar-track{height:9px;border-radius:5px;background:var(--surface);margin-top:7px;overflow:hidden}
.rep-bar-fill{height:100%;border-radius:5px;-webkit-print-color-adjust:exact;print-color-adjust:exact}
.rep-bar-foot{font-family:var(--font-mono);font-size:9px;color:var(--muted);margin-top:5px}

/* Stats: gráfico de tendencia (barras verticales) */
.rep-chart{display:flex;align-items:flex-end;gap:14px;height:170px;
  padding:8px 4px 0;border-bottom:1px solid var(--hairline)}
.rep-chart-col{flex:1;display:flex;flex-direction:column;align-items:center;
  justify-content:flex-end;height:100%;gap:6px}
.rep-chart-amt{font-size:9px;color:var(--muted);white-space:nowrap}
.rep-chart-barwrap{width:100%;flex:1;display:flex;align-items:flex-end;justify-content:center}
.rep-chart-bar{width:62%;max-width:46px;border-radius:5px 5px 0 0;min-height:2px;
  -webkit-print-color-adjust:exact;print-color-adjust:exact}
.rep-chart-lbl{font-family:var(--font-mono);font-size:9px;letter-spacing:.1em;
  text-transform:uppercase;color:var(--muted)}
"""
