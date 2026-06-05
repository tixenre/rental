"""Tokens visuales + helpers compartidos de los mails — **fuente ÚNICA**.

Los clientes de mail no soportan CSS vars ni `oklch` ni fuentes vendoreadas de
forma confiable → acá mapeamos, una sola vez, los tokens del Design System
(`docs/DESIGN_SYSTEM.md`) a **hex web-safe** + stacks de fuente con fallback. El
wrapper branded (`service._wrap_email_html`), los bodies por defecto
(`default_templates`), la tabla de ítems (`routes/alquileres` + el preview de
`routes/email_templates`) y las migraciones de repintado importan de acá —
nada de hex sueltos "parecidos pero distintos" repetidos por archivo
(barra de calidad #1: modularidad a prueba de balas, `docs/MEMORIA.md`).

**Por qué hex y no los tokens crudos del DS:** `--amber` ya es hex y se usa tal
cual; el resto son `oklch` que ningún cliente de mail entiende. Los valores de
abajo son la conversión fiel de esos `oklch` a sRGB, con dos matices anotados
(ink y bone) para confort de lectura en pantalla de mail.
"""
from __future__ import annotations

# ── Paleta (token del DS → hex de mail) ───────────────────────────────────────
AMBER = "#FAB428"     # --amber: brand accent (barra, botón CTA, highlights). Token exacto.
INK = "#1f1a14"       # --ink: warm near-black para headings/body/strong y texto sobre amber.
#                       --ink puro computa a ~#0c0806 (casi negro); lo llevamos a una L de
#                       lectura cómoda (~0.17) manteniendo el hue cálido 60.
MUTED = "#6b6457"     # --muted-foreground: texto secundario, párrafos atenuados.
FAINT = "#8a8378"     # fine print del footer (ink a baja densidad).
BONE = "#faf8f3"      # --background (bone): fondo exterior del mail. (--bg computa a ~#fbfaf6;
#                       dejamos un punto más cálido para que la card blanca resalte.)
SURFACE = "#f6f3ec"   # --surface: footer y zonas tintadas.
HAIRLINE = "#e6e2d9"  # --hairline (ink @ 12%): bordes y divisores.
CARD = "#ffffff"      # --surface-elevated: cuerpo del mail (card).

# ── Tipografía ────────────────────────────────────────────────────────────────
# TT Commons / Champ Black no cargan confiable en mail → se acepta el fallback de
# sistema (decisión del prompt). Los eyebrows/labels SÍ respetan la receta del DS
# (mono, uppercase, tracking ancho) porque la stack monospace está disponible en
# todos los clientes.
FONT_SANS = "Arial,Helvetica,sans-serif"
FONT_MONO = "'JetBrains Mono','Courier New',monospace"

# ── Estilos inline reutilizables (atributo `style="…"` completo) ──────────────
H = f'style="margin:0 0 12px;font-family:{FONT_SANS};font-size:19px;font-weight:bold;color:{INK};"'
LBL = (
    f'style="margin:18px 0 6px;font-family:{FONT_MONO};color:{MUTED};font-size:11px;'
    'text-transform:uppercase;letter-spacing:.1em;"'
)
TOTAL = f'style="margin:6px 0 4px;font-size:16px;color:{INK};font-variant-numeric:tabular-nums;"'
MUTED_P = f'style="margin:18px 0 0;color:{MUTED};font-size:14px;"'


def btn(url_var: str, label: str) -> str:
    """Botón CTA primario (amber) bulletproof: table-based + inline para mail.

    `url_var` es el nombre de la variable Jinja del href (ej. `portal_url`) → el
    string devuelto la deja como `{{ url_var }}` para que la renderice la plantilla.
    """
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" style="margin:18px 0;">'
        f'<tr><td style="border-radius:8px;background:{AMBER};">'
        f'<a href="{{{{ {url_var} }}}}" style="display:inline-block;padding:12px 24px;'
        f'font-family:{FONT_SANS};font-size:15px;font-weight:bold;'
        f'color:{INK};text-decoration:none;">{label}</a></td></tr></table>'
    )


def btn_secondary(url_var: str, label: str) -> str:
    """Botón CTA secundario (contorno) para no competir con el primario."""
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 18px;">'
        f'<tr><td style="border-radius:8px;border:1px solid {HAIRLINE};">'
        f'<a href="{{{{ {url_var} }}}}" style="display:inline-block;padding:11px 22px;'
        f'font-family:{FONT_SANS};font-size:14px;font-weight:bold;'
        f'color:{INK};text-decoration:none;">{label}</a></td></tr></table>'
    )


def item_row(nombre_html: str, cantidad_html: str, subtotal_html: str | None) -> str:
    """Una fila de la tabla de ítems del mail. Los tres args ya vienen
    escapados/seguros desde el caller (datos dinámicos) — acá solo se les da
    forma. `subtotal_html=None` deja la celda vacía (ej. mail de admin sin total
    por ítem)."""
    sub_cell = (
        f'<td style="padding:8px 0;text-align:right;white-space:nowrap;'
        f'color:{INK};font-variant-numeric:tabular-nums;">{subtotal_html}</td>'
        if subtotal_html is not None
        else '<td style="padding:8px 0;"></td>'
    )
    return (
        f'<tr style="border-bottom:1px solid {HAIRLINE};">'
        f'<td style="padding:8px 8px 8px 0;color:{INK};">{nombre_html}</td>'
        f'<td style="padding:8px 12px;text-align:center;color:{MUTED};white-space:nowrap;">'
        f'× {cantidad_html}</td>'
        f"{sub_cell}</tr>"
    )


def items_table(rows_html: str) -> str:
    """Envuelve filas (de `item_row`) en la tabla de ítems. Devuelve '' si no hay
    filas (el body lo inyecta con `|safe`)."""
    if not rows_html:
        return ""
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="border-collapse:collapse;font-size:14px;margin:4px 0 8px;">'
        f"{rows_html}</table>"
    )
