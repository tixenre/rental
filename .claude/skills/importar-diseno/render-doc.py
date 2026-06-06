#!/usr/bin/env python3
"""render-doc.py — rasteriza un DOCUMENTO PDF del repo a PNG para verlo.

El análogo de `render.mjs`, pero para los PDF (que no son rutas web: se generan
server-side importando una función-template de Python y rasterizando su HTML con
Playwright). Sirve para el render-compare de un handoff de documentos: render del
documento REAL actual → comparar contra el mockup → implementar → re-renderizar.

Uso (desde la raíz del repo, con el venv del backend activo):

    source backend/.venv/bin/activate
    python .claude/skills/importar-diseno/render-doc.py presupuesto
    python .claude/skills/importar-diseno/render-doc.py reportes --out /tmp/rep.png

Documentos: presupuesto · albaran · contrato · packing · reportes · todos
Flags: --out <path> (default /tmp/doc-<tipo>.png) · --width <px> (default 820)

El script imprime `PNG: /tmp/...` por cada render → Claude lee ese PNG con la tool
de imágenes y lo compara con el mockup.

**El dato de muestra (`_PEDIDO` / `_STATS`) es deliberadamente RICO** —ítems con
specs en el nombre (" · " → línea INCLUYE), componentes, contenido_incluido,
serie, valor_reposicion, fecha_compra, cliente responsable inscripto— para que
los 5 documentos rindan todas sus partes. Si el modelo de datos del repo gana un
campo que un documento muestra, sumalo acá para que el render lo ejercite.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# El backend del repo (donde viven pdf.py / pdf_templates.py) relativo a este skill.
_REPO = Path(__file__).resolve().parents[3]
_BACKEND = _REPO / "backend"
sys.path.insert(0, str(_BACKEND))


def _cont(*names):
    return [{"nombre": n, "cantidad": 1} for n in names]


# Pedido de muestra compartido por los 4 documentos de pedido.
_PEDIDO = {
    "estado": "confirmado", "numero_pedido": 42, "emitido": "2026-06-04",
    "cliente_nombre": "Productora Faro Audiovisual S.R.L.",
    "cliente_cuit": "30-71234567-8", "cliente_email": "produccion@faroav.com.ar",
    "cliente_telefono": "223 612-4488", "cliente_direccion": "Av. Colón 2384, Mar del Plata",
    "cliente_razon_social": "Faro Audiovisual S.R.L.",
    "cliente_perfil_impuestos": "responsable_inscripto",
    "fecha_desde": "2026-06-12", "fecha_hasta": "2026-06-15", "cantidad_jornadas": 3,
    "descuento_pct": 10, "bruto": 384000, "monto_neto": 345600,
    "notas": "Retiro el 12/6 a las 9:00 hs. Devolución hasta las 18:00 hs del 15/6. "
             "Se incluye asesoramiento técnico en el armado.",
    "items": [
        {"nombre_publico": "Cámara Sony FX6 · Cuerpo FX6 · Correa de mano · Tapa de montura · Cable USB-C · Manija XLR",
         "cantidad": 1, "precio_jornada": 45000, "serie": "FX6-AA1043",
         "valor_reposicion": 4200000, "fecha_compra": "2023-03-15",
         "contenido_incluido": _cont("Cuerpo FX6", "Correa de mano", "Tapa de montura", "Cable USB-C", "Manija XLR"),
         "componentes": [
             {"nombre_publico": "Batería Sony BP-U70", "cantidad": 2, "valor_reposicion": 95000},
             {"nombre_publico": "Cargador doble Sony BC-U2", "cantidad": 1, "valor_reposicion": 70000}]},
        {"nombre_publico": "Lente Sony FE 24-70mm f/2.8 GM II · Lente · Parasol · Tapas delantera y trasera · Estuche blando",
         "cantidad": 1, "precio_jornada": 18000, "serie": "2470-GM7782",
         "valor_reposicion": 2600000, "fecha_compra": "2023-06-01",
         "contenido_incluido": _cont("Lente", "Parasol", "Tapas delantera y trasera", "Estuche blando")},
        {"nombre_publico": "Iluminación Aputure LS 600x Pro · Cabezal · Balastro · Reflector · Cable de poder",
         "cantidad": 2, "precio_jornada": 22000, "serie": "APT600-3391 / 3392",
         "valor_reposicion": 1800000, "fecha_compra": "2024-01-10",
         "contenido_incluido": _cont("Cabezal", "Balastro", "Reflector", "Cable de poder"),
         "componentes": [
             {"nombre_publico": "Aputure Light Dome III", "cantidad": 2, "valor_reposicion": 280000},
             {"nombre_publico": "Pie C-stand 3.3 m con grip arm", "cantidad": 2, "valor_reposicion": 150000}]},
        {"nombre_publico": "Monitor-grabador Atomos Shogun 7 · Monitor · Batería NP-F · Cable HDMI · Parasol",
         "cantidad": 1, "precio_jornada": 9000, "serie": "SHG7-1120",
         "valor_reposicion": 980000, "fecha_compra": "2023-09-20",
         "contenido_incluido": _cont("Monitor", "Batería NP-F", "Cable HDMI", "Parasol")},
        {"nombre_publico": "Estabilizador DJI RS 4 Pro · Gimbal · Trípode integrado · Cargador · Cables de control · Valija",
         "cantidad": 1, "precio_jornada": 12000, "serie": "RS4-5567",
         "valor_reposicion": 1150000, "fecha_compra": "2024-02-18",
         "contenido_incluido": _cont("Gimbal", "Trípode integrado", "Cargador", "Cables de control", "Valija")},
    ],
}

# Datos de muestra para el Resumen general del reporte (espeja compute_estadisticas).
_STATS = {
    "totales": {"total_pedidos": 18, "total_clientes": 14, "total_ars": 2480000},
    "por_mes": [
        {"mes": "2025-12", "pedidos": 9, "total_ars": 1740000},
        {"mes": "2026-01", "pedidos": 8, "total_ars": 1520000},
        {"mes": "2026-02", "pedidos": 10, "total_ars": 1880000},
        {"mes": "2026-03", "pedidos": 12, "total_ars": 2060000},
        {"mes": "2026-04", "pedidos": 13, "total_ars": 2204000},
        {"mes": "2026-05", "pedidos": 18, "total_ars": 2480000},
    ],
    "crecimiento": [{"mes": "2026-05", "total_ars": 2480000, "crecimiento_pct": 12.5}],
    "por_dueno": [
        {"dueno": "Rambla", "total_ars": 1612000, "items": 42},
        {"dueno": "Pablo", "total_ars": 546000, "items": 18},
        {"dueno": "Tincho", "total_ars": 322000, "items": 11},
    ],
    "top_clientes": [
        {"cliente": "Productora Faro Audiovisual S.R.L.", "pedidos": 4, "total_ars": 612000},
        {"cliente": "Productora Sur", "pedidos": 3, "total_ars": 398000},
        {"cliente": "Estudio Marea", "pedidos": 2, "total_ars": 246000},
        {"cliente": "Lucía Brandt", "pedidos": 2, "total_ars": 188000},
    ],
}


def _html_for(tipo: str) -> str:
    """HTML del documento pedido, importando la función-template canónica del repo."""
    import pdf_templates as t
    if tipo == "presupuesto":
        return t._pedido_html(_PEDIDO)
    if tipo == "albaran":
        return t._albaran_html(_PEDIDO)
    if tipo == "contrato":
        return t._contrato_html(_PEDIDO)
    if tipo == "packing":
        return t._packing_list_html(_PEDIDO)
    if tipo == "reportes":
        from pdf import _liquidacion_html
        data = {
            "beneficiarios": ["Rambla", "Pablo", "Tincho"],
            "resumen": {"por_beneficiario": {"Rambla": 742000, "Pablo": 318000, "Tincho": 196000},
                        "total": 1256000},
            "por_mes": [], "por_dueno": [
                {"dueno": "Rambla", "monto_generado": 742000, "pedidos": 7,
                 "reparto": {"Rambla": 742000},
                 "equipos": [{"equipo": "Cámara Sony FX6", "veces": 4, "monto": 360000},
                             {"equipo": "Lente Sony FE 24-70 GM II", "veces": 3, "monto": 180000}]},
                {"dueno": "Tincho", "monto_generado": 280000, "pedidos": 2,
                 "reparto": {"Tincho": 196000, "Rambla": 84000},
                 "equipos": [{"equipo": "Micrófono Sennheiser MKH 416", "veces": 5, "monto": 160000}]},
            ],
        }
        return _liquidacion_html(data, "junio de 2026", stats=_STATS)
    raise SystemExit(f"tipo desconocido: {tipo}")


async def _shot(htmlstr: str, out: str, width: int) -> None:
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": width, "height": 1160}, device_scale_factor=2)
        await pg.set_content(htmlstr, wait_until="networkidle")
        await pg.screenshot(path=out, full_page=True)
        await b.close()


_TIPOS = ["presupuesto", "albaran", "contrato", "packing", "reportes"]


def main() -> None:
    ap = argparse.ArgumentParser(description="Rasteriza un documento PDF del repo a PNG.")
    ap.add_argument("tipo", choices=_TIPOS + ["todos"])
    ap.add_argument("--out", default=None)
    ap.add_argument("--width", type=int, default=820)
    args = ap.parse_args()
    tipos = _TIPOS if args.tipo == "todos" else [args.tipo]
    for tipo in tipos:
        out = args.out if (args.out and args.tipo != "todos") else f"/tmp/doc-{tipo}.png"
        asyncio.run(_shot(_html_for(tipo), out, args.width))
        print(f"PNG: {out}")


if __name__ == "__main__":
    main()
