"""
pdf_templates.py — Plantillas de documentos Rambla Rental (rediseño DS v1)
==========================================================================

DROP-IN para `backend/pdf.py`. Reemplazá las cuatro funciones de template
( `_pedido_html` · `_albaran_html` · `_contrato_html` · `_packing_list_html` )
por las de este módulo. El resto de `pdf.py` queda IGUAL:
`_render_pdf`, `_get_browser`, `_abs_image_url`, `_pedido_filename`,
y los helpers de `services.precios` (`jornadas_periodo`,
`es_responsable_inscripto`, `IVA_PCT`).

Qué cambia respecto del template anterior
------------------------------------------
- Tipografía del Design System:
    · TT Commons   → toda la UI (body, headings, labels)
    · JetBrains Mono → precios, fechas, N° de serie, IDs, eyebrows (tabular)
    · Champ Black  → SOLO el wordmark "rambla"
  (Antes: Nunito + Space Mono + Helvetica.)
- Amber de marca real **#FAB428** (antes #F9B92E) y paleta de ESTADO oficial
  (verde #009971 Confirmado, azul #1097DB Presupuesto, rosa #ED7BAD Devuelto,
  naranja #E9552F, destructive Cancelado).
- Wordmark real de Rambla (SVG) en el membrete, teñido en `ink`.
- Tokens de color / sombra / radio del DS. Sin gradientes, single-accent.
- Descripciones largas (`nombre_publico_largo`) → cabecera + specs como lista
  compacta de tags (en vez de un string con "·" muy largo).
- Fechas con día de la semana ("vie 12/06/2026").

Fuentes
-------
TT Commons y Champ Black están vendoreadas en el repo (src/assets/fonts/).
Playwright renderiza con base `about:blank`, así que las embebemos en base64
vía `_fonts_css()`. Ajustá `FONTS_DIR` si tu layout difiere. JetBrains Mono
se trae de Google Fonts (igual que el catálogo).

Variantes
---------
El default es el membrete "filete" (sobrio, ideal para impresión) + caja de
totales en `ink` con total en amber (la firma de marca). Para una caja de
totales clara con total en negro, mirá `.total-box--light` al final del CSS.
"""

import base64
import html
import json
import os
from datetime import datetime, date

# Helpers de precios del repo — mismos imports que el pdf.py original.
try:
    from services.precios import jornadas_periodo, es_responsable_inscripto, IVA_PCT
except Exception:  # pragma: no cover — fallback para correr el módulo aislado
    IVA_PCT = 21
    def jornadas_periodo(d1, d2):
        try:
            return max(1, (d2 - d1).days)
        except Exception:
            return 1
    def es_responsable_inscripto(perfil):
        return str(perfil or "").lower().startswith("responsable")

# Datos del locador (env vars en producción)
OWNER_NOMBRE    = os.getenv("OWNER_NOMBRE",    "Marín Javier Santini Calarco")
OWNER_CUIL      = os.getenv("OWNER_CUIL",      "23-37389102-9")
OWNER_DIRECCION = os.getenv("OWNER_DIRECCION", "Falucho 4625, Mar del Plata")
OWNER_TELEFONO  = os.getenv("OWNER_TELEFONO",  "223 590-9080")
OWNER_EMAIL     = os.getenv("OWNER_EMAIL",     "ramblarental@gmail.com")
OWNER_WEB       = os.getenv("OWNER_WEB",       "ramblarental.com.ar")

# Directorio de fuentes vendoreadas (ajustar al layout real del repo)
FONTS_DIR = os.getenv(
    "PDF_FONTS_DIR",
    os.path.join(os.path.dirname(__file__), "..", "src", "assets", "fonts"),
)

# Archivo : (family, weight)  — TT Commons familia + Champ Black display
_FONT_FILES = [
    ("TT_Commons_Regular_0.otf",  "TT Commons", 400, "opentype"),
    ("TT_Commons_Medium_0.otf",   "TT Commons", 500, "opentype"),
    ("TT_Commons_DemiBold_0.otf", "TT Commons", 600, "opentype"),
    ("TT_Commons_Bold_0.otf",     "TT Commons", 700, "opentype"),
    ("TT_Commons_Black_0.otf",    "TT Commons", 900, "opentype"),
    ("Champ-Black.ttf",           "Champ Black", 900, "truetype"),
]


def _fonts_css() -> str:
    """Embebe las fuentes vendoreadas como @font-face base64 (Playwright)."""
    faces = []
    for fname, family, weight, fmt in _FONT_FILES:
        path = os.path.join(FONTS_DIR, fname)
        try:
            with open(path, "rb") as fh:
                b64 = base64.b64encode(fh.read()).decode("ascii")
        except OSError:
            continue  # si falta una fuente, cae al stack del sistema
        mime = "font/otf" if fmt == "opentype" else "font/ttf"
        faces.append(
            f"@font-face{{font-family:'{family}';font-weight:{weight};"
            f"font-style:normal;font-display:swap;"
            f"src:url(data:{mime};base64,{b64}) format('{fmt}')}}"
        )
    return "<style>" + "".join(faces) + "</style>"


# Wordmark "rambla" — fill currentColor para teñir por contexto (ink)
WORDMARK = (
    '<svg viewBox="0 0 3625.42 686.57" fill="currentColor" role="img" '
    'aria-label="Rambla" preserveAspectRatio="xMinYMid meet" '
    'style="height:34px;width:auto;display:block">'
    '<path d="M1549.97,464.87c51.57,0,111.41-130.76,131.22-183.31,5.55-14.72,23.28-6.63,18.2,7.87-38.22,109.24-98.59,397.13,64.78,397.13,200.66,0,84.74-686.29-10.63-686.29-62.44,0-141.94,155.28-189.56,274.31-5.22,13.06-22.81,13.07-28.05.02C1488.1,155.58,1407.51.28,1345.06.28c-95.37,0-211.3,686.29-10.63,686.29,163.38,0,103-287.89,64.78-397.13-5.07-14.5,12.65-22.59,18.2-7.87,19.81,52.55,80.98,183.31,132.56,183.31Z"/>'
    '<path d="M2699.82.28c298.65,0-44.31,535.29-44.31,535.29-5.22,10.95,5.6,20.31,15.55,10.68,0,0,303.92-326.09,317.17-73.34,0,0,5.6,197.62-62.95,197.62h-358.88c-5.22,0-10-3.61-11.58-8.82C2539.59,611.5,2488.94.28,2699.82.28Z"/>'
    '<path d="M871.63,32.09c-166.08-91.26-277.58,32.24-272.91,120.09,3.84,72.29,45.18,95.24,166.85,59.33,92.86-27.4,164.14-20.76,175.6-10.89,4.99,4.29,4.76,18.03-16.56,18.03-142.75,0-289.12,110.65-326.92,238.67-37.81,128.02,47.27,231,190.01,230.01,62.56-.43,125.82-20.78,180.32-54.26l-4.32,36.35h75.64c120.04,0,125.65-135.14,133.19-240.71,14.18-198.43-45.22-512.62-300.92-396.61ZM975.09,394.67c-21.2,50.04-87.38,95.61-147.81,101.79-60.43,6.18-92.24-29.37-71.03-79.41,21.2-50.04,87.38-95.61,147.81-101.79,60.43-6.18,92.24,29.37,71.03,79.41Z"/>'
    '<path d="M3322.55,32.09c-166.08-91.26-277.58,32.24-272.91,120.09,3.84,72.29,45.18,95.24,166.85,59.33,92.86-27.4,164.14-20.76,175.6-10.89,4.99,4.29,4.76,18.03-16.56,18.03-142.75,0-289.12,110.65-326.92,238.67-37.81,128.02,47.27,231,190.01,230.01,62.56-.43,125.82-20.78,180.32-54.26l-4.32,36.35h75.64c120.04,0,125.65-135.14,133.19-240.71,14.18-198.43-45.22-512.62-300.92-396.61ZM3426.01,394.67c-21.2,50.04-87.38,95.61-147.81,101.79-60.43,6.18-92.24-29.37-71.03-79.41,21.2-50.04,87.38-95.61,147.81-101.79,60.43-6.18,92.24,29.37,71.03,79.41Z"/>'
    '<path d="M208.25,500.64c3.75.2,7.53.46,11.37.57,145.64,3.88,291.41-101.72,325.57-235.87C579.34,131.18,488.97,4.16,343.33.28c-52.42-1.4-107.99,20.82-151.97,49.92-6.25,4.14-14.55-1.73-13.93-9.2.42-5.14.87-10.28,1.34-15.43.51-5.5-3.78-10.25-9.3-10.25H8.91s-24.66,307.78,8.05,573.56c5.67,46.05,44.97,80.53,91.37,80.53h109s-5.01-30.23-11.71-70.8c0,0,140.32,146.02,330.37,60.93v-208.07c0-7.57-8.11-12.4-14.72-8.73-46.73,25.9-195.61,100.72-314.03,75.8-15.02-3.16-14.11-18.7,1.01-17.91ZM176.73,325.76c21.2-50.04,87.38-95.61,147.81-101.79,60.43-6.18,92.24,29.37,71.03,79.41-21.2,50.04-87.38,95.61-147.81,101.79-60.43,6.18-92.24-29.37-71.03-79.41Z"/>'
    '<path d="M2397.44,267.74c16.09-22.07,28.67-45.82,36.22-70.7C2467.48,85.5,2391.38.28,2263.68.28c-41.5,0-93.47,16.99-142.57,48.83-9.51,6.17-16.58-1.16-15.39-12.43.34-3.21.67-6.36.98-9.24.66-6.17-4.18-11.5-10.39-11.5h-159.24s-24.59,329.4,7.92,590.73c5.69,45.74,44.76,79.97,90.85,79.97,7.82,0,26.94-.07,34.96-.07,258.71,0,372.59-112.26,407.93-228.83,25.63-84.53-9.35-156.86-81.3-190ZM2104.5,257.82c18.34-43.29,75.6-82.72,127.88-88.06,52.28-5.35,79.8,25.41,61.45,68.7-1.48,3.5-3.31,6.96-5.28,10.4-59.1,3.18-117.97,24.97-167.81,58.82-5.49,3.73-13.06,2.27-16.43-3.45-7.09-12.03-7.59-28.07.18-46.4ZM2336.37,488.72c-19.47,45.96-80.26,87.82-135.76,93.49-55.5,5.68-84.71-26.98-65.24-72.93,19.47-45.96,80.26-87.82,135.76-93.49,55.51-5.68,84.71,26.98,65.24,72.93Z"/>'
    '</svg>'
)

# Paleta de ESTADO (EstadoBadge oficial) → (color, fondo soft)
_ESTADOS = {
    "borrador":    ("oklch(0.42 0.01 70)", "color-mix(in oklch, oklch(0.42 0.01 70) 14%, transparent)"),
    "presupuesto": ("#1097DB", "color-mix(in oklch, #1097DB 14%, transparent)"),
    "confirmado":  ("#009971", "color-mix(in oklch, #009971 14%, transparent)"),
    "retirado":    ("#FAB428", "color-mix(in oklch, #FAB428 18%, transparent)"),
    "devuelto":    ("#ED7BAD", "color-mix(in oklch, #ED7BAD 16%, transparent)"),
    "cancelado":   ("oklch(0.62 0.22 27)", "color-mix(in oklch, oklch(0.62 0.22 27) 14%, transparent)"),
}

# ── Hoja de estilos del documento (tokens del DS, A4 print) ──────────────────
_DOC_CSS = r"""
:root{
  --amber:#FAB428; --amber-soft:color-mix(in oklch,#FAB428 18%,transparent);
  --ink:oklch(0.14 0.01 60); --muted:oklch(0.42 0.01 70);
  --hairline:oklch(0.18 0.01 60 / 12%);
  --surface:oklch(0.97 0.008 85); --bg:#fff;
  --font-sans:"TT Commons",ui-sans-serif,system-ui,sans-serif;
  --font-mono:"JetBrains Mono",ui-monospace,monospace;
  --r-sm:8px; --r-md:10px; --r-lg:12px;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
@page{size:A4;margin:14mm}
body{font-family:var(--font-sans);color:var(--ink);background:#fff;
  -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
.paper{display:flex;flex-direction:column;min-height:269mm}

/* Membrete (filete) */
.membrete{margin-bottom:30px}
.mb-top{display:flex;justify-content:space-between;align-items:flex-start;gap:28px}
.mb-brand{display:flex;flex-direction:column;gap:8px}
.mb-wordmark{color:var(--ink)}
.mb-tagline{font-family:var(--font-mono);font-size:9.5px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--muted);white-space:nowrap}
.mb-doc{display:flex;flex-direction:column;align-items:flex-end;text-align:right;gap:3px;flex-shrink:0}
.mb-eyebrow{font-family:var(--font-mono);font-size:9.5px;letter-spacing:.22em;
  text-transform:uppercase;color:var(--muted);white-space:nowrap}
.mb-type{font-weight:700;font-size:26px;letter-spacing:-.01em;line-height:1;white-space:nowrap}
.mb-num{font-family:var(--font-mono);font-weight:600;font-size:15px;margin-top:4px;white-space:nowrap}
.mb-date{font-family:var(--font-mono);font-size:10.5px;color:var(--muted);margin-top:2px;white-space:nowrap}
.mb-rule{height:3px;background:var(--amber);border-radius:2px;margin-top:22px}

.estado-badge{display:inline-flex;align-items:center;gap:6px;margin-top:10px;
  font-family:var(--font-mono);font-size:9.5px;font-weight:700;letter-spacing:.12em;
  text-transform:uppercase;padding:4px 11px 4px 9px;border-radius:9999px}
.estado-badge .dot{width:6px;height:6px;border-radius:50%}

/* Meta */
.meta{display:grid;grid-template-columns:1fr 1fr;gap:22px 28px;margin-bottom:28px}
.meta-block{display:flex;flex-direction:column;gap:4px;min-width:0}
.meta-label{font-family:var(--font-mono);font-size:9px;letter-spacing:.16em;
  text-transform:uppercase;color:var(--muted);margin-bottom:3px}
.meta-val{font-weight:600;font-size:15px;line-height:1.3}
.meta-sub{font-size:11.5px;color:var(--muted);line-height:1.5}
.meta-sub.mono{font-family:var(--font-mono)}
.meta-accent{font-family:var(--font-mono);font-size:11px;font-weight:600;
  color:color-mix(in oklch,var(--amber) 78%,var(--ink));margin-top:3px}

.callout{margin-bottom:22px;padding:13px 16px;border-radius:var(--r-md);
  background:var(--surface);border:1px solid var(--hairline);
  font-size:11.5px;line-height:1.6;color:var(--muted)}
.callout b{color:var(--ink);font-weight:600}

/* Tabla de items */
.items{width:100%;border-collapse:collapse}
.items thead th{font-family:var(--font-mono);font-size:9px;font-weight:600;
  letter-spacing:.14em;text-transform:uppercase;color:var(--muted);
  text-align:left;padding:0 12px 10px;border-bottom:1.5px solid var(--ink)}
.items th.r,.items td.r{text-align:right}
.items th.c,.items td.c{text-align:center}
.items tbody td{padding:12px;border-bottom:1px solid var(--hairline);
  vertical-align:middle;font-size:13px;line-height:1.4}
.items tbody tr:last-child td{border-bottom:1.5px solid var(--ink)}
.items .eq-name{font-weight:600;color:var(--ink)}
.items td.mono,.items .mono{font-family:var(--font-mono);font-variant-numeric:tabular-nums}
.items td.num{font-family:var(--font-mono);font-variant-numeric:tabular-nums}
.items td.num,.items td.r{white-space:nowrap}
.items .comp td{color:var(--muted)}
.items .comp .eq-name{font-weight:500;color:var(--muted)}
.comp-mark{color:color-mix(in oklch,var(--amber) 70%,var(--ink));
  font-family:var(--font-mono);margin-right:4px}
.eq-thumb{width:46px;height:46px;border-radius:var(--r-sm);object-fit:cover;
  background:var(--surface);border:1px solid var(--hairline);display:flex;
  align-items:center;justify-content:center;color:var(--muted);flex-shrink:0}
.eq-thumb.sm{width:36px;height:36px}

/* Specs como lista compacta */
.spec-list{list-style:none;display:flex;flex-direction:column;gap:1px;margin-top:5px;padding:0}
.spec-list li{font-family:var(--font-mono);font-size:9.5px;line-height:1.5;color:var(--muted);
  padding-left:11px;position:relative}
.spec-list li::before{content:"·";position:absolute;left:2px;font-weight:700;
  color:color-mix(in oklch,var(--amber) 65%,var(--ink))}

/* Totales (ink) */
.total-section{display:flex;justify-content:flex-end;margin-top:22px}
.total-box{min-width:300px;background:var(--ink);color:#fff;border-radius:var(--r-lg);
  padding:20px 24px;-webkit-print-color-adjust:exact;print-color-adjust:exact}
.total-row{display:flex;justify-content:space-between;align-items:baseline;gap:28px;padding:5px 0}
.total-row .tl{font-family:var(--font-mono);font-size:10px;letter-spacing:.1em;
  text-transform:uppercase;color:oklch(1 0 0 / .6);white-space:nowrap}
.total-row .tv{font-family:var(--font-mono);font-variant-numeric:tabular-nums;
  font-size:13px;color:oklch(1 0 0 / .92);white-space:nowrap}
.total-row.grand{border-top:1px solid oklch(1 0 0 / .18);margin-top:8px;padding-top:14px}
.total-row.grand .tl{color:#fff;font-size:11px}
.total-row.grand .tv{font-family:var(--font-sans);font-weight:800;font-size:26px;
  color:var(--amber);letter-spacing:-.01em}
.total-foot{font-family:var(--font-mono);font-size:9.5px;color:oklch(1 0 0 / .5);
  text-align:right;margin-top:10px;letter-spacing:.04em}
/* Variante clara opcional: agregá class="total-box--light" a .total-box */
.total-box--light{background:#fff;color:var(--ink);border:1.5px solid var(--ink)}
.total-box--light .total-row .tl{color:var(--muted)}
.total-box--light .total-row .tv{color:var(--ink)}
.total-box--light .total-row.grand{border-top-color:var(--ink)}
.total-box--light .total-row.grand .tl{color:var(--ink)}
.total-box--light .total-foot{color:var(--muted)}

/* Notas */
.notas{margin-top:26px;padding:14px 18px;background:var(--amber-soft);
  border-left:3px solid var(--amber);border-radius:0 var(--r-md) var(--r-md) 0;
  font-size:12px;line-height:1.6;color:color-mix(in oklch,var(--ink) 78%,transparent)}
.notas-label{font-family:var(--font-mono);font-size:9px;letter-spacing:.16em;
  text-transform:uppercase;color:color-mix(in oklch,var(--amber) 55%,var(--ink));margin-bottom:5px}

/* Firmas */
.firmas{display:grid;grid-template-columns:1fr 1fr;gap:48px;margin-top:56px}
.firma{border-top:1.5px solid var(--ink);padding-top:9px}
.firma .rol{font-family:var(--font-mono);font-size:9px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--muted)}
.firma .name{font-size:12.5px;font-weight:600;margin-top:3px}
.firma .sub{font-size:11px;color:var(--muted);margin-top:1px}

/* Footer */
.doc-footer{margin-top:auto;padding-top:22px;border-top:1px solid var(--hairline);
  display:flex;justify-content:space-between;align-items:center;gap:14px;
  font-family:var(--font-mono);font-size:9.5px;letter-spacing:.04em;color:var(--muted)}
.doc-footer .fb{color:var(--ink);font-weight:600}

/* Section heading */
.sec-head{display:flex;align-items:baseline;gap:10px;margin:30px 0 14px}
.sec-head .sec-title{font-weight:700;font-size:16px}
.sec-head .sec-meta{font-family:var(--font-mono);font-size:10px;color:var(--muted);
  letter-spacing:.04em;white-space:nowrap}
.sec-head .sec-line{flex:1;height:1px;background:var(--hairline)}

/* Contrato */
.partes{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:24px}
.parte{border:1px solid var(--hairline);border-radius:var(--r-lg);padding:16px 18px;background:var(--surface)}
.parte-head{font-family:var(--font-mono);font-size:9px;letter-spacing:.16em;text-transform:uppercase;
  color:color-mix(in oklch,var(--amber) 55%,var(--ink));padding-bottom:9px;margin-bottom:11px;
  border-bottom:1px solid var(--hairline)}
.parte-row{margin-bottom:9px}
.parte-k{font-family:var(--font-mono);font-size:8.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
.parte-v{font-size:12.5px;font-weight:500;margin-top:1px}
.clausulas{columns:2;column-gap:28px;margin-top:6px}
.clausula{break-inside:avoid;margin-bottom:11px;font-size:9.5px;line-height:1.65;
  color:color-mix(in oklch,var(--ink) 80%,transparent);text-align:justify}
.clausula b{color:var(--ink);font-weight:700}
.clausula-intro{font-size:10.5px;line-height:1.65;color:color-mix(in oklch,var(--ink) 82%,transparent);
  margin-bottom:16px;text-align:justify}
.clausula-intro b{color:var(--ink)}

/* Packing */
.pk-legend{display:flex;gap:16px;margin-bottom:16px;font-family:var(--font-mono);font-size:10px;color:var(--muted)}
.pk-legend span{display:inline-flex;align-items:center;gap:6px}
.pk-box{width:13px;height:13px;border:1.5px solid var(--ink);border-radius:3px;display:inline-block}
.items.packing td.chk{text-align:center;width:70px}
.pk-check{width:16px;height:16px;border:1.5px solid var(--ink);border-radius:4px;display:inline-block}
.items.packing .row-cont td{padding:5px 12px 12px;border-bottom:1px dashed var(--hairline)}
.cont-list{display:flex;flex-wrap:wrap;align-items:center;gap:5px 8px;padding-left:58px}
.cont-label{font-family:var(--font-mono);font-size:8.5px;letter-spacing:.14em;text-transform:uppercase;
  color:color-mix(in oklch,var(--amber) 55%,var(--ink));margin-right:2px}
.cont-item{display:inline-flex;align-items:center;gap:5px;font-family:var(--font-mono);font-size:9.5px;color:var(--muted)}
.cont-item .cb{width:11px;height:11px;border:1px solid var(--hairline);border-radius:3px;flex-shrink:0}
.pk-summary{display:flex;justify-content:space-between;align-items:center;margin-top:24px;
  padding:16px 20px;border-radius:var(--r-lg);background:var(--surface);border:1px solid var(--hairline)}
.pk-stat{display:flex;flex-direction:column;gap:2px}
.pk-stat .n{font-family:var(--font-mono);font-weight:700;font-size:22px;font-variant-numeric:tabular-nums}
.pk-stat .l{font-family:var(--font-mono);font-size:9px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
"""

# ── Helpers de formato (espejan los de pdf.py; reusá los del repo al mergear) ─
_MESES = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto",
          "septiembre","octubre","noviembre","diciembre"]
_DOW = ["lun","mar","mié","jue","vie","sáb","dom"]


def _as_dt(s):
    if not s:
        return None
    if hasattr(s, "strftime"):
        return s
    try:
        return datetime.fromisoformat(str(s))
    except ValueError:
        return None


def _fmt_ars(n, zero_dash=False):
    try:
        v = int(float(n or 0))
    except Exception:
        return html.escape(str(n)) if n else "—"
    if v == 0:
        return "—" if zero_dash else "$ 0"
    return "$ " + f"{v:,}".replace(",", ".")


def _fmt_date_short(s):
    d = _as_dt(s)
    return d.strftime("%d/%m/%Y") if d else "—"


def _fmt_date_dow(s):
    """'vie 12/06/2026' — fecha corta con día de la semana."""
    d = _as_dt(s)
    return f"{_DOW[d.weekday()]} {d.strftime('%d/%m/%Y')}" if d else "—"


def _fmt_date_long(s):
    d = _as_dt(s)
    return f"{d.day} de {_MESES[d.month - 1]} de {d.year}" if d else "—"


def _nombre_para_pdf(item, formal=False):
    publico = (item.get("nombre_publico") or "").strip()
    largo = (item.get("nombre_publico_largo") or "").strip()
    nombre = (item.get("nombre") or "").strip()
    marca = (item.get("marca") or "").strip()
    if formal and largo:
        return largo
    if publico:
        return publico
    if largo:
        return largo
    if marca and marca.lower() not in nombre.lower():
        return f"{marca} {nombre}".strip() or "—"
    return nombre or "—"


def _nombre_rich(item, formal=False, mark=False):
    """Cabecera en negrita + specs ('·') como lista de tags compacta."""
    parts = _nombre_para_pdf(item, formal=formal).split(" · ")
    mk = '<span class="comp-mark">└</span>' if mark else ""
    out = f'<div class="eq-name">{mk}{html.escape(parts[0])}</div>'
    if len(parts) > 1:
        tags = "".join(f"<li>{html.escape(p)}</li>" for p in parts[1:])
        out += f'<ul class="spec-list">{tags}</ul>'
    return out


def _thumb(item, sm=False):
    cls = "eq-thumb sm" if sm else "eq-thumb"
    # Resolvé foto_url con el helper canónico de pdf.py (absolutiza paths
    # relativos para Playwright, que renderiza con base about:blank). Import
    # perezoso: rompe el ciclo (pdf.py importa este módulo).
    from pdf import _abs_image_url
    url = _abs_image_url((item.get("foto_url") or "").strip())
    if url:
        return f'<img class="{cls}" src="{html.escape(url)}" alt="">'
    cam = ('<svg width="20" height="20" viewBox="0 0 24 24" fill="none" '
           'stroke="currentColor" stroke-width="1.5" stroke-linecap="round" '
           'stroke-linejoin="round"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/>'
           '<circle cx="12" cy="13" r="3"/></svg>')
    return f'<div class="{cls}">{cam}</div>'


def _ref(pedido):
    if pedido.get("numero_pedido"):
        return f"R-{int(pedido['numero_pedido']):04d}"
    return f"#{pedido.get('id', '—')}"


def _membrete(pedido, doc_type, num, fecha, estado=True):
    badge = ""
    if estado and pedido.get("estado") in _ESTADOS:
        color, soft = _ESTADOS[pedido["estado"]]
        label = pedido["estado"].capitalize()
        badge = (f'<span class="estado-badge" style="color:{color};background:{soft};'
                 f'border:1px solid color-mix(in oklch,{color} 28%,transparent)">'
                 f'<span class="dot" style="background:{color}"></span>{label}</span>')
    return (
        '<header class="membrete"><div class="mb-top">'
        f'<div class="mb-brand"><span class="mb-wordmark">{WORDMARK}</span>'
        '<div class="mb-tagline">Alquiler de equipos audiovisuales</div></div>'
        '<div class="mb-doc"><div class="mb-eyebrow">Documento</div>'
        f'<div class="mb-type">{html.escape(doc_type)}</div>'
        f'<div class="mb-num">N° {html.escape(num)}</div>'
        f'<div class="mb-date">Emitido {html.escape(fecha)}</div>{badge}</div>'
        '</div><div class="mb-rule"></div></header>'
    )


def _footer():
    return (
        '<footer class="doc-footer"><span class="fb">Rambla Rental</span>'
        f'<span>{html.escape(OWNER_DIRECCION)} · {html.escape(OWNER_TELEFONO)}</span>'
        f'<span>{html.escape(OWNER_WEB)}</span></footer>'
    )


def _cliente_block(pedido):
    out = ['<div class="meta-block"><div class="meta-label">Cliente</div>'
           f'<div class="meta-val">{html.escape(pedido.get("cliente_nombre") or "—")}</div>']
    if pedido.get("cliente_cuit"):
        out.append(f'<div class="meta-sub mono">CUIT {html.escape(pedido["cliente_cuit"])}</div>')
    if pedido.get("cliente_email"):
        out.append(f'<div class="meta-sub">{html.escape(pedido["cliente_email"])}</div>')
    if pedido.get("cliente_telefono"):
        out.append(f'<div class="meta-sub mono">{html.escape(pedido["cliente_telefono"])}</div>')
    out.append("</div>")
    return "".join(out)


def _document(body):
    head = (
        '<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">'
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">'
        + _fonts_css() + "<style>" + _DOC_CSS + "</style></head><body>"
    )
    return head + '<article class="paper">' + body + "</article></body></html>"


def _jornadas(pedido):
    j = pedido.get("cantidad_jornadas") or pedido.get("jornadas")
    if j:
        return int(j)
    try:
        return jornadas_periodo(_as_dt(pedido["fecha_desde"]), _as_dt(pedido["fecha_hasta"]))
    except Exception:
        return 1


# ═══════════════════════════════════════════════════════════════════════════
#  PRESUPUESTO   (reemplaza _pedido_html)
# ═══════════════════════════════════════════════════════════════════════════
def _pedido_html(pedido):
    j = _jornadas(pedido)
    items = pedido.get("items", [])
    rows = []
    for it in items:
        sub = (it.get("precio_jornada") or 0) * it.get("cantidad", 1) * j
        rows.append(
            f'<tr><td style="width:58px">{_thumb(it)}</td>'
            f'<td><div class="eq-name">{html.escape(_nombre_para_pdf(it))}</div></td>'
            f'<td class="c num">{it.get("cantidad", 1)}</td>'
            f'<td class="r num">{_fmt_ars(it.get("precio_jornada"))}</td>'
            f'<td class="r num">{_fmt_ars(sub)}</td></tr>'
        )
        for c in it.get("componentes", []):
            cant = c.get("cantidad", 1) * it.get("cantidad", 1)
            csub = (c.get("precio_jornada") or 0) * cant * j
            rows.append(
                f'<tr class="comp"><td></td>'
                f'<td><span class="comp-mark">└</span>{html.escape(_nombre_para_pdf(c))}</td>'
                f'<td class="c num">{cant}</td>'
                f'<td class="r num">{_fmt_ars(c.get("precio_jornada")) if c.get("precio_jornada") else "incluido"}</td>'
                f'<td class="r num">{_fmt_ars(csub) if csub else "—"}</td></tr>'
            )

    # Desglose — usa el precomputado por services.precios (igual que el original)
    es_ri = es_responsable_inscripto(pedido.get("cliente_perfil_impuestos"))
    iva_pct = int(pedido.get("iva_pct") or IVA_PCT)
    neto = int(pedido["monto_neto"] if pedido.get("monto_neto") is not None
               else (pedido.get("monto_total") or _sum_bruto(items, j)))
    bruto = int(pedido.get("bruto") or _sum_bruto(items, j) or neto)
    desc_pct = float(pedido.get("descuento_pct") or 0)
    desc = int(pedido["descuento_monto"] if pedido.get("descuento_monto") is not None
               else max(0, bruto - neto))
    if pedido.get("monto_neto") is None and desc:
        neto = bruto - desc
    iva = int(pedido["iva_monto"] if pedido.get("iva_monto") is not None
              else (round(neto * iva_pct / 100) if es_ri else 0))
    total = neto + iva

    tr = [f'<div class="total-row"><span class="tl">Subtotal</span><span class="tv">{_fmt_ars(bruto)}</span></div>']
    if desc > 0:
        pct = f" ({desc_pct:g}%)" if desc_pct else ""
        tr.append(f'<div class="total-row"><span class="tl">Descuento{pct}</span><span class="tv">− {_fmt_ars(desc)}</span></div>')
    if es_ri:
        if desc > 0:
            tr.append(f'<div class="total-row"><span class="tl">Neto</span><span class="tv">{_fmt_ars(neto)}</span></div>')
        tr.append(f'<div class="total-row"><span class="tl">IVA {iva_pct}%</span><span class="tv">{_fmt_ars(iva)}</span></div>')
    tr.append(f'<div class="total-row grand"><span class="tl">Total</span><span class="tv">{_fmt_ars(total)}</span></div>')

    notas = ""
    if pedido.get("notas"):
        notas = f'<div class="notas"><div class="notas-label">Notas</div>{html.escape(pedido["notas"])}</div>'

    fa = " · Factura A · IVA discriminado" if es_ri else ""
    periodo = (
        '<div class="meta-block"><div class="meta-label">Período de alquiler</div>'
        f'<div class="meta-val">{_fmt_date_dow(pedido.get("fecha_desde"))} → {_fmt_date_dow(pedido.get("fecha_hasta"))}</div>'
        f'<div class="meta-accent">{j} jornada{"s" if j != 1 else ""}{fa}</div></div>'
    )
    body = (
        _membrete(pedido, "Presupuesto", _ref(pedido), _fmt_date_long(pedido.get("emitido") or datetime.now()))
        + f'<div class="meta">{_cliente_block(pedido)}{periodo}</div>'
        + '<table class="items"><thead><tr><th></th><th>Equipo</th>'
          '<th class="c">Cant.</th><th class="r">Precio / jornada</th><th class="r">Subtotal</th></tr></thead>'
          f'<tbody>{"".join(rows)}</tbody></table>'
        + '<div class="total-section"><div><div class="total-box">' + "".join(tr) + "</div>"
        + f'<div class="total-foot">{j} jornada{"s" if j != 1 else ""} · '
          f'{len(items)} equipo{"s" if len(items) != 1 else ""}{" · Factura A" if es_ri else ""}</div></div></div>'
        + notas + _footer()
    )
    return _document(body)


def _sum_bruto(items, j):
    total = 0
    for it in items:
        total += (it.get("precio_jornada") or 0) * it.get("cantidad", 1) * j
        for c in it.get("componentes", []):
            total += (c.get("precio_jornada") or 0) * c.get("cantidad", 1) * it.get("cantidad", 1) * j
    return total


# ═══════════════════════════════════════════════════════════════════════════
#  ALBARÁN   (reemplaza _albaran_html)
# ═══════════════════════════════════════════════════════════════════════════
def _albaran_html(pedido):
    items = pedido.get("items", [])
    valor_total, n, unidades, rows = 0, 1, 0, []

    def _valor(unit, cant):
        if cant <= 1:
            return f'<span class="num">{_fmt_ars(unit)}</span>'
        return (f'<div class="num"><div style="font-size:10px;color:var(--muted)">'
                f'{_fmt_ars(unit)} × {cant}</div>'
                f'<div style="font-weight:600">{_fmt_ars(unit * cant)}</div></div>')

    for it in items:
        cant = it.get("cantidad", 1); unidades += cant
        valor = _parse_int(it.get("valor_reposicion")); valor_total += valor * cant
        rows.append(
            f'<tr><td class="c num" style="width:34px">{n}</td>'
            f'<td style="width:54px">{_thumb(it, True)}</td>'
            f'<td>{_nombre_rich(it, formal=True)}</td>'
            f'<td class="c num">{cant}</td>'
            f'<td class="mono">{html.escape(it.get("serie") or "—")}</td>'
            f'<td class="r">{_valor(valor, cant)}</td></tr>'
        ); n += 1
        for c in it.get("componentes", []):
            ccant = c.get("cantidad", 1) * cant; unidades += ccant
            cvalor = _parse_int(c.get("valor_reposicion")); valor_total += cvalor * ccant
            rows.append(
                f'<tr class="comp"><td class="c num">{n}</td>'
                f'<td>{_thumb(c, True)}</td>'
                f'<td>{_nombre_rich(c, formal=True, mark=True)}</td>'
                f'<td class="c num">{ccant}</td>'
                f'<td class="mono">{html.escape(c.get("serie") or "—")}</td>'
                f'<td class="r">{_valor(cvalor, ccant)}</td></tr>'
            ); n += 1

    entrega = (
        '<div class="meta-block"><div class="meta-label">Entrega / devolución</div>'
        f'<div class="meta-val">{_fmt_date_dow(pedido.get("fecha_desde"))} → {_fmt_date_dow(pedido.get("fecha_hasta"))}</div>'
        f'<div class="meta-sub">Retiro en {html.escape(OWNER_DIRECCION)}</div></div>'
    )
    body = (
        _membrete(pedido, "Albarán", _ref(pedido), _fmt_date_short(pedido.get("emitido") or datetime.now()))
        + f'<div class="meta">{_cliente_block(pedido)}{entrega}</div>'
        + '<table class="items"><thead><tr><th class="c">#</th><th></th><th>Equipo</th>'
          '<th class="c">Cant.</th><th>N° Serie</th><th class="r">Valor reposición</th></tr></thead>'
          f'<tbody>{"".join(rows)}</tbody></table>'
        + '<div class="total-section"><div class="total-box" style="min-width:320px">'
          f'<div class="total-row"><span class="tl">Equipos entregados</span><span class="tv">{unidades} unidades</span></div>'
          f'<div class="total-row grand"><span class="tl">Valor total de reposición</span><span class="tv">{_fmt_ars(valor_total)}</span></div>'
          '<div class="total-foot">Suma de cantidad × valor unitario, incluyendo componentes de kits.</div></div></div>'
        + '<div class="firmas">'
          f'<div class="firma"><div class="rol">Firma cliente</div><div class="name">{html.escape(pedido.get("cliente_nombre") or "—")}</div><div class="sub">Aclaración / DNI</div></div>'
          f'<div class="firma"><div class="rol">Por Rambla Rental</div><div class="name">{html.escape(OWNER_NOMBRE)}</div><div class="sub">Aclaración / DNI</div></div></div>'
        + _footer()
    )
    return _document(body)


def _parse_int(v):
    if v in (None, ""):
        return 0
    try:
        return int(float(str(v).replace("$", "").replace(".", "").replace(",", "").strip() or 0))
    except Exception:
        return 0


# ═══════════════════════════════════════════════════════════════════════════
#  CONTRATO   (reemplaza _contrato_html)
# ═══════════════════════════════════════════════════════════════════════════
_CLAUSULAS_INTRO = ("<b>El Locador y el Locatario</b>, cuya individualización surge del frente del "
    "presente contrato de locación de cosas muebles no fungibles, resuelven celebrar el mismo de "
    "acuerdo con las normas establecidas por el art. 1499 del Código Civil, y que se regirá por las "
    "siguientes cláusulas y condiciones:")

_CLAUSULAS = [
    ("Primero", "El locatario declara recibir en locación los objetos que se detallan en este contrato y que forman parte del mismo de plena conformidad y en perfecto estado de funcionamiento, por haberlos probado en el acto de recepción, obligándose a su restitución en el plazo indicado y en las mismas condiciones de funcionamiento."),
    ("Segundo", "El plazo de la locación como así también su destino es el que surge del frente del presente contrato y de igual modo su precio es el establecido por las tarifas vigentes, que el locatario declara conocer."),
    ("Tercero", "Los bienes locados, objetos de este contrato, deberán ser devueltos en el plazo y domicilio indicado por la locadora."),
    ("Cuarto", "En caso de incumplimiento a lo establecido en el artículo precedente, el locatario pagará a la locadora por cada día de demora, incluidos los feriados, el precio de alquiler pactado con una recarga del 50% de dicha suma, en concepto de cláusula penal, que se operará de pleno derecho por mero vencimiento del plazo pactado, sin necesidad de interpelación alguna."),
    ("Quinto", "El locatario ha probado y reconoce el perfecto funcionamiento de los bienes locados, y en consecuencia, el locador no asume responsabilidad alguna sobre el resultado de los trabajos que se efectúen con dichos elementos."),
    ("Sexto", "El locatario se obliga y a su costa a custodiar y mantener en perfectas condiciones los bienes; asimismo a su costa el reemplazo y/o reparación de las piezas, mecanismos y/o partes afectadas que impidan el uso normal de los equipos, por otras legítimas de las marcas que correspondan. Las reparaciones se efectuarán en los términos que el locador indique en la emergencia."),
    ("Séptimo", "Para el supuesto del artículo precedente jugarán las condiciones previstas en el artículo «Cuarto» respecto al pago de la locación por cada día de demora y sus recargos, hasta el día en que los elementos estén perfectamente reparados y entregados de conformidad del locador. Esto sin perjuicio del pago de las reparaciones a costa del locatario."),
    ("Octavo", "El locatario se hace responsable por los daños y perjuicios que pudieran sufrir los bienes, ya sea por caso fortuito, fuerza mayor, culpa o hecho de terceros, así como por cualquier daño y/o perjuicio que sufran terceros por causa emanada de los equipos alquilados o sus operaciones."),
    ("Noveno", "En caso de pérdida, destrucción o rotura de los bienes durante la duración del contrato, el locatario se obliga a reponer cualquiera o todos los elementos dañados, o a abonar al locador su valor según los comercios de plaza más caracterizados o sus importadores, con las pertinentes cargas impositivas, aduaneras y fletes."),
    ("Décimo", "El locatario se obliga a no trasladar los bienes locados a una distancia mayor de 100 km de Mar del Plata, a no ser que el locador preste su conformidad por escrito para ese traslado."),
    ("Undécimo", "Queda absolutamente prohibido al locatario subalquilar, prestar, dar en comodato o desprenderse de cualquier manera de la tenencia de los objetos dados en locación. Estos deberán ser operados por personal técnico o idóneo a criterio del locador."),
    ("Duodécimo", "El precio de locación se pagará a los treinta días, sin perjuicio de los plazos y recargos por mora precedentemente previstos."),
    ("Decimotercero — Jurisdicción", f"Para todos los efectos judiciales y extrajudiciales derivados del presente contrato, el locador constituye domicilio en {OWNER_DIRECCION}, y el locatario en el domicilio indicado en el frente. Ambas partes se someten a la competencia ordinaria de los Tribunales del Departamento Judicial de Mar del Plata."),
    ("Decimocuarto — Seguro", "El locatario deberá contratar el correspondiente seguro sobre los objetos de locación individualizados, a su exclusivo costo."),
]


def _contrato_html(pedido):
    items = pedido.get("items", [])
    j = _jornadas(pedido)
    rows, i = [], 1
    for it in items:
        cant = it.get("cantidad", 1)
        rows.append(
            f'<tr><td class="c num">{i}</td>'
            f'<td>{_nombre_rich(it, formal=True)}</td>'
            f'<td class="c num">{cant}</td>'
            f'<td class="mono">{html.escape(it.get("serie") or "—")}</td>'
            f'<td class="r num">{_fmt_ars(_parse_int(it.get("valor_reposicion")))}</td></tr>'
        ); i += 1
        for c in it.get("componentes", []):
            ccant = c.get("cantidad", 1) * cant
            rows.append(
                f'<tr class="comp"><td class="c">—</td>'
                f'<td>{_nombre_rich(c, formal=True, mark=True)}</td>'
                f'<td class="c num">{ccant}</td>'
                f'<td class="mono">{html.escape(c.get("serie") or "—")}</td>'
                f'<td class="r num">{_fmt_ars(_parse_int(c.get("valor_reposicion"))) if c.get("valor_reposicion") else "—"}</td></tr>'
            )

    es_ri = es_responsable_inscripto(pedido.get("cliente_perfil_impuestos"))
    ri_extra = ""
    if es_ri:
        ri_extra = (
            f'<div class="parte-row"><div class="parte-k">Razón social</div><div class="parte-v">{html.escape(pedido.get("cliente_razon_social") or "—")}</div></div>'
            f'<div class="parte-row"><div class="parte-k">CUIT</div><div class="parte-v">{html.escape(pedido.get("cliente_cuit") or "—")}</div></div>'
            '<div class="parte-row"><div class="parte-k">Condición IVA</div><div class="parte-v">Responsable Inscripto</div></div>'
        )
    fecha_long = _fmt_date_long(pedido.get("emitido") or datetime.now())
    clausulas = "".join(f'<p class="clausula"><b>{html.escape(t)}.</b> {b}</p>' for t, b in _CLAUSULAS)

    body = (
        _membrete(pedido, "Contrato", _ref(pedido), fecha_long, estado=False)
        + '<div class="meta">'
          '<div class="meta-block"><div class="meta-label">Período de locación</div>'
          f'<div class="meta-val">{_fmt_date_dow(pedido.get("fecha_desde"))} al {_fmt_date_dow(pedido.get("fecha_hasta"))}</div></div>'
          '<div class="meta-block"><div class="meta-label">Duración</div>'
          f'<div class="meta-val">{j} jornada{"s" if j != 1 else ""}</div></div></div>'
        + '<div class="partes"><div class="parte"><div class="parte-head">Locador</div>'
          f'<div class="parte-row"><div class="parte-k">Nombre</div><div class="parte-v">{html.escape(OWNER_NOMBRE)}</div></div>'
          f'<div class="parte-row"><div class="parte-k">CUIL</div><div class="parte-v">{html.escape(OWNER_CUIL)}</div></div>'
          f'<div class="parte-row"><div class="parte-k">Domicilio</div><div class="parte-v">{html.escape(OWNER_DIRECCION)}</div></div>'
          f'<div class="parte-row"><div class="parte-k">Contacto</div><div class="parte-v">{html.escape(OWNER_TELEFONO)} · {html.escape(OWNER_EMAIL)}</div></div></div>'
          '<div class="parte"><div class="parte-head">Locatario</div>'
          f'<div class="parte-row"><div class="parte-k">Nombre</div><div class="parte-v">{html.escape(pedido.get("cliente_nombre") or "—")}</div></div>'
          f'<div class="parte-row"><div class="parte-k">Domicilio</div><div class="parte-v">{html.escape(pedido.get("cliente_direccion") or "—")}</div></div>'
          f'<div class="parte-row"><div class="parte-k">Contacto</div><div class="parte-v">{html.escape(pedido.get("cliente_telefono") or "—")} · {html.escape(pedido.get("cliente_email") or "—")}</div></div>'
          f'{ri_extra}</div></div>'
        + '<div class="sec-head"><span class="sec-title">Equipos a alquilar</span><span class="sec-line"></span><span class="sec-meta">valor reposición ARS</span></div>'
        + '<table class="items"><thead><tr><th class="c">#</th><th>Equipo</th>'
          '<th class="c">Cant.</th><th>N° Serie</th><th class="r">Reposición</th></tr></thead>'
          f'<tbody>{"".join(rows)}</tbody></table>'
        + '<div class="sec-head"><span class="sec-title">Cláusulas y condiciones</span><span class="sec-line"></span></div>'
        + f'<p class="clausula-intro">{_CLAUSULAS_INTRO}</p>'
        + f'<div class="clausulas">{clausulas}</div>'
        + '<div class="firmas">'
          f'<div class="firma"><div class="rol">Firma Locatario</div><div class="name">{html.escape(pedido.get("cliente_nombre") or "—")}</div><div class="sub">Aclaración / DNI</div></div>'
          f'<div class="firma"><div class="rol">Firma Locador</div><div class="name">{html.escape(OWNER_NOMBRE)}</div><div class="sub">Aclaración / DNI</div></div></div>'
        + f'<div style="text-align:center;font-family:var(--font-mono);font-size:10px;color:var(--muted);margin-top:28px;letter-spacing:.04em">Emitido en Mar del Plata, {fecha_long}</div>'
        + _footer()
    )
    return _document(body)


# ═══════════════════════════════════════════════════════════════════════════
#  PACKING LIST   (reemplaza _packing_list_html)
# ═══════════════════════════════════════════════════════════════════════════
def _contenido_list(item):
    """Lista de strings de 'contenido incluido' para los chips del packing.

    El repo guarda `contenido_incluido_json` (string JSON con una lista de
    **objetos** `{nombre, cantidad, ...}`); el reference usaba `contenido_incluido`
    como lista de strings. Acepta ambas formas y devuelve strings listos para
    mostrar ("Cable USB-C" o "Cable USB-C ×2"). JSON inválido → [] (no rompe).
    """
    raw = item.get("contenido_incluido")
    if not isinstance(raw, list):
        s = item.get("contenido_incluido_json")
        if not s:
            return []
        try:
            raw = json.loads(s)
        except (ValueError, TypeError):
            return []
    if not isinstance(raw, list):
        return []
    out = []
    for x in raw:
        if isinstance(x, dict):
            nombre = (x.get("nombre") or x.get("nombre_publico") or "").strip()
            if not nombre:
                continue
            cant = x.get("cantidad") or 1
            out.append(f"{nombre} ×{cant}" if cant and cant != 1 else nombre)
        elif x not in (None, ""):
            out.append(str(x))
    return out


def _packing_list_html(pedido):
    items = pedido.get("items", [])
    rows, n, unidades = [], 1, 0

    def _row(it, sub=False):
        cant = it.get("cantidad", 1)
        cls = ' class="comp"' if sub else ""
        num = "" if sub else n
        return (
            f'<tr{cls}><td class="c num" style="width:34px">{num}</td>'
            f'<td style="width:50px">{_thumb(it, True)}</td>'
            f'<td>{_nombre_rich(it, formal=True, mark=sub)}</td>'
            f'<td class="c num">{cant}</td>'
            '<td class="chk"><span class="pk-check"></span></td>'
            '<td class="chk"><span class="pk-check"></span></td></tr>'
        )

    for it in items:
        cant = it.get("cantidad", 1); unidades += cant
        rows.append(_row(it)); n += 1
        for c in it.get("componentes", []):
            ccant = c.get("cantidad", 1) * cant; unidades += ccant
            cc = dict(c); cc["cantidad"] = ccant
            rows.append(_row(cc, sub=True))
        cont = _contenido_list(it)
        if cont:
            chips = "".join(f'<span class="cont-item"><span class="cb"></span>{html.escape(x)}</span>' for x in cont)
            rows.append('<tr class="row-cont"><td></td><td colspan="5">'
                        f'<div class="cont-list"><span class="cont-label">Incluye</span>{chips}</div></td></tr>')

    salida = (
        '<div class="meta-block"><div class="meta-label">Salida / retorno</div>'
        f'<div class="meta-val">{_fmt_date_dow(pedido.get("fecha_desde"))} → {_fmt_date_dow(pedido.get("fecha_hasta"))}</div>'
        f'<div class="meta-accent">{unidades} unidades a controlar</div></div>'
    )
    body = (
        _membrete(pedido, "Packing List", _ref(pedido), _fmt_date_short(pedido.get("emitido") or datetime.now()))
        + f'<div class="meta">{_cliente_block(pedido)}{salida}</div>'
        + '<div class="pk-legend"><span><span class="pk-box"></span> Salida — control al retirar</span>'
          '<span><span class="pk-box"></span> Retorno — control al devolver</span></div>'
        + '<table class="items packing"><thead><tr><th class="c">#</th><th></th>'
          '<th>Equipo / contenido</th><th class="c">Cant.</th><th class="chk">Salida</th><th class="chk">Retorno</th></tr></thead>'
          f'<tbody>{"".join(rows)}</tbody></table>'
        + '<div class="pk-summary">'
          f'<div class="pk-stat"><span class="n">{len(items)}</span><span class="l">Equipos principales</span></div>'
          f'<div class="pk-stat"><span class="n">{unidades}</span><span class="l">Unidades totales</span></div>'
          f'<div class="pk-stat"><span class="n">{_jornadas(pedido)}</span><span class="l">Jornadas</span></div></div>'
        + '<div class="firmas">'
          '<div class="firma"><div class="rol">Controló salida</div><div class="name">&nbsp;</div><div class="sub">Nombre · fecha · hora</div></div>'
          '<div class="firma"><div class="rol">Controló retorno</div><div class="name">&nbsp;</div><div class="sub">Nombre · fecha · hora</div></div></div>'
        + _footer()
    )
    return _document(body)
