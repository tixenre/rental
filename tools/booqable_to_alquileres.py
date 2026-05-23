#!/usr/bin/env python3
"""
Convierte un export de Booqable (orders + lines + products + customers) al
formato `alquileres.json` que importa /admin/dataio/import.

Decisiones de mapping consolidadas con el operador (ver MAPPING dict).
Productos archived en Booqable que aparecen como combo parents son ignorados
(la composicion real esta en las child lines via parent_line_id).

Uso:
    python3 tools/booqable_to_alquileres.py \\
        --orders     /path/orders.csv \\
        --lines      /path/lines.csv \\
        --products   /path/products.csv \\
        --customers  /path/customers.csv \\
        --equipos    /path/equipos.json \\
        --outdir     /path/out

Output en --outdir:
    alquileres.zip                  -- listo para /admin/dataio/import (scope=operacional)
    placeholders.sql                -- SQL para crear los placeholder equipos antes
    placeholders.json               -- mismos placeholders en JSON
    skipped.csv                     -- pedidos saltados (canceled, sin cliente, etc.)
    report.txt                      -- resumen humano-legible

PASOS para el operador:
    1. Pegar placeholders.sql en Railway DB (crea los equipos historicos)
    2. Subir alquileres.zip en /admin/dataio (import operacional)
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
import zipfile
from pathlib import Path
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# MAPPING explicito (decidido con el operador). Klave: booqable product slug
# o titulo exacto de linea archived. Valor: local equipo slug + multiplicador.
# ─────────────────────────────────────────────────────────────────────────────

# Mappings por slug Booqable (productos activos). Keys = slug EXACTO de Booqable.
MAPPING_BY_BOOQABLE_SLUG: dict[str, tuple[str, int]] = {
    # (booqable_slug → local_slug, qty_multiplier)
    # ── Confirmados explicitamente con el operador ─────────────────────
    "alargue": ("extension-electrica", 1),
    "canon-lp6-bateria": ("canon-lp-e6p", 1),
    "bateria-serie-l-np": ("smallrig-l-series-np-f970", 1),
    "cable-sdi-20-cm": ("elvid-bncrr-020-c2", 1),
    "godox-m1-rgb": ("godox-m1", 1),
    "godox-softbox-bolachina": ("godox-cs85d", 1),
    "small-hd-monitor-7": ("smallhd-702-touch", 1),
    "frame-2x2mts": ("frame-2x2", 1),  # Tela Difu 2x2mts
    "carl-zeiss-jena-vintage-kit-20-35-50-y-135-mm": ("carl-zeiss-jena-20-35-50-135mm-m42", 1),
    "carro-dolly-de-9mts": ("manfrotto-riel-carro-9mts", 1),
    "dji-sdr-transmisor-inalambrico": ("dji-sdr-transmission-combo", 1),
    "dji-wireles-mic": ("dji-mic-dual-transmitter", 1),
    "bateria-sony-z": ("sony-np-fz100", 1),  # Bateria Sony Z100
    "estudio-combo-illuminacion-y-griperia": ("estudio-equipos-promo", 1),
    "avenger-d650-boom": ("avenger-d650", 1),
    "avenger-brazo-con-rotula": ("avenger-d520l", 1),  # Avenger D520 Brazo
    "avenger-grip-head-d200": ("avenger-d200", 1),
    "avenger-c500": ("avenger-c500-grande", 1),
    "back-drop-tripodes-barral-y-tela": ("backdrop-negro-kit-soporte", 1),  # Negro 4x5mts
    "amaran-200c-bicolor": ("amaran-200x", 1),
    "avenger-c-stand-arana-2-7mts": ("avenger-a2016d", 1),  # base desmontable 2.75mts
    "avenger-c-stand-arana-2-7mts-no-3-5mts": ("avenger-a2016d", 1),  # base fija 3.5mts (unidas)
    "avenger-combo-steel-stand-35-3-5mts": ("avenger-a1035cs", 1),
    "lilliput-monitor-17-de-produccion-con-carrying-case": ("lilliput-bm150-4k", 1),
    "manfrotto-monopie": ("manfrotto-mvmxproa4us", 1),
    "sony-7-v": ("sony-a7-v", 1),
    "bandera-rebote-difucion": ("bandera-negra-40x60cm", 1),  # 1x1mts
    "bandera-rebote-difucion-30x50cm": ("bandera-negra-40x60cm", 1),  # negro 30x50
    "bandera-rebote-difucion-difucion-rebote-30x50": ("bandera-negra-40x60cm", 1),
    "bandera-rebote-difucion-difucion-rebote-40x60": ("bandera-negra-40x60cm", 1),
    "bandera-rebote-difucion-negra-40x60cm": ("bandera-negra-40x60cm", 1),
    "bateria-vmount-ikan-99wh": ("anton-bauer-v-mount-x4-cargador", 1),
    "vmount-x3-con-cargador": ("anton-bauer-v-mount-x4-cargador", 1),  # Cargador Ikan C2KS
    "cargador-baterias-sony": ("sony-bc-zd1", 1),
    "5en1-reflector-oval-plegable-1-x-1-85-mts": ("godox-5en1", 1),
    "5en1-reflector-redondo-1mts": ("godox-redondo-1mts", 1),
    "smallhd-monitor-5": ("blackmagic-video-assist-5", 1),  # nombre real: BlackMagic Monitor 5"
    "godox-tl60": ("godox-tl60-rgb-led-tube-light", 1),

    # ── Auto-matches obvios (token overlap < 0.7 pero claramente correctos) ──
    "aputure-softbox-iii": ("aputure-quick-dome-90", 1),
    "aputure-softbox-light-dome-mini-ii": ("aputure-softbox-mini-ii", 1),
    "arri-fresnel-650w-kit-3-und": ("arri-650-plus", 3),  # kit de 3 → expandir
    "canon-c200": ("canon-eos-c200", 1),
    "dji-ronin-s3-pro": ("dji-rs-4-pro", 1),
    "ef-e-adaptador-sigma-m11": ("sigma-mc-11", 1),
    "ef-rf-adaptador": ("canon-drop-in-filter-mount-adapter-ef-eos-r-con-filtro-nd-variable", 1),
    "ef-rf-adaptador-solo-adaptador": ("canon-ef-rf", 1),
    "estudio": ("rambla-estudio", 1),
    "hollyland-solidcom-c1-sistema-de-intercomunicadores-wireless-con-4-headsets-1-9-ghz": ("hollyland-solidcom-c1-4s", 1),
    "insta360-x4-8k": ("insta360-x4", 1),
    "manfrotto-502-hd": ("manfrotto-mvh502a-y-546b", 1),
    "manfrotto-504-tripode-camara": ("manfrotto-mvh502a-fluid-head-y-mvt502am-tripod", 1),
    "nanlite-fresnel-fl-206": ("nanlite-fl-20g", 1),
    "portkeys-monitor-5-5": ("portkeys-bm5-5-5", 1),
    "rode-ntg2-shotgun": ("rode-ntg2", 1),
    "rode-videomic-go-ii-boom-camera": ("rode-videomic-go-ii-h", 1),
    "rodecaster-video": ("rode-rodecaster-video", 1),
    "sigma-art-18-35mm-f1-8-apsc": ("sigma-18-35mm-f-1-8-dc-hsm-art", 1),
    "sigma-art-24-70mm-f2-8-montura-e": ("sigma-24-70mm-f-2-8-dg-os-hsm-art", 1),
    "small-righ-vmount-50": ("smallrig-vb50-mini-v-mount-battery", 1),
    "small-righ-vmount-99": ("smallrig-vb99", 1),
    "softbox-angler-120cm": ("angler-quick-open-deep-parabolic-softbox-v2-48", 1),
    "sony-gm-12-24-f2-8": ("sony-fe-12-24mm-f-2-8-gm", 1),
    "switch-craft-cana-fibra-carbono-zepeling": ("switch-craft-cana-zeppelin", 1),
    "tarjeta-de-memoria-angelbird-cfexpress-tipo-b-de-1tb": ("red-1tb-pro-cfexpress-v4-type-b-memory-card", 1),
    "tarjeta-sd": ("sony-sf-g128t-t1", 1),  # Sony Tough 128gb V90
    "tarjeta-sd-angelbird-256-v30-sd": ("angelbird-av-pro-sd-v30-256gb", 1),
    "tarjeta-sd-sandisk-256-gb-v90-sd": ("sandisk-256gb-extreme-pro-uhs-ii-sdxc", 1),
    "pinza-de-metal": ("impact-ssc-a20b", 1),  # Pinzas Grandes
    "tilta-gravity-gx2": ("tilta-gravity-g2x", 1),
    "tilta-hydra-ventosa-electronica-4-5": ("tilta-hydra-x-dan-ming-speed-pan-system", 1),
    "tilta-nucleus-nano-ii-inalambrico": ("tilta-nucleus-nano-ii-wireless-lens-control-system-with-control-handle-kit", 1),
    "tokina-11-16mm-f2-8-apsc": ("tokina-11-16mm-f-2-8-ef", 1),
    "yongnuo-on-camera-yn300-bicolor": ("yongnuo-yn300-bicolor", 1),
}

# Mappings por TITULO exacto de linea (para productos archived que no estan en
# products.csv pero aparecen en lines como simple).
MAPPING_BY_LINE_TITLE: dict[str, tuple[str, int]] = {
    "Godox TL60 1und": ("godox-tl60-rgb-led-tube-light", 1),
    "Godox TL60 Kit de 4": ("godox-tl60-rgb-led-tube-light", 4),
    "Tubos Godox TL60 Kit de 4und": ("godox-tl60-rgb-led-tube-light", 4),  # por si aparece como simple
    "Tarjeta SD Sand Disk 128 gb v30": ("sandisk-sdsdxxd-128g-ancin", 1),
    "alargues": ("extension-electrica", 1),
    "Cable SDI - 20cm": ("elvid-bncrr-020-c2", 1),
    "Cargador Baterias Sony": ("sony-bc-zd1", 1),
    "Rode Podcast Mics": ("rode-procaster", 1),
    "Rodecaster Audio": ("rode-rodecaster-video", 1),
    "Bandera Negra 60x90": ("ox-grips-bandera-negra", 1),
    "Cable HDMI - 5mts": ("kondor-blue-kb-fhdmi-12-bk", 1),
    "Car Mount con Cabezal Anti-vibracion": ("car-mount", 1),
    "Marco 1x1": ("kupo-kg094012", 1),  # Marco Difusion
    "Bateria NP tipo sony": ("smallrig-l-series-np-f970", 1),
    "Baterias LP": ("canon-lp-e6p", 1),  # Canon LP-E6
    "Rode Link Mic": ("rode-lavalier", 1),  # archived Booqable "Rode Link" — uso lavalier
    "Aputure Softbox Light Dome SE": ("aputure-softbox-mini-ii", 1),
}

# Slugs Booqable que van EXPLICITAMENTE a placeholder (no mapeables)
EXPLICIT_PLACEHOLDERS: set[str] = {
    "anton-bauer-titon-90-v-mount",          # Bateria Anton/Bauer Titon 90
    "red-digital-cinema-dsmc3-red-5-pin-lemo-to-3-5mm-female-audio-adapter-11-3",  # RED 5-pin
}

# Titulos archived que van a placeholder
PLACEHOLDER_BY_TITLE: set[str] = {
    "Sony FX30",
}

# Statuses Booqable a importar (skip canceled segun decision del operador)
STATUSES_TO_IMPORT = {"stopped", "started", "reserved"}

# Umbral minimo de token-overlap para auto-match (0.0-1.0). Bajar = mas
# matches automaticos (riesgo de falsos positivos). 0.7 es bastante estricto.
TOKEN_OVERLAP_THRESHOLD = 0.7

# Tokens ruidosos que se ignoran para el matching token-based
STOP_TOKENS = {
    "camara","cámara","camera","gimbal","luz","light","lente","lens",
    "softbox","fresnel","tungsteno","tungsten","monitor","tripode","trípode",
    "bateria","batería","cargador","charger","reflector","adaptador",
    "transmisor","receptor","grabadora","micrófono","microfono","mic",
    "cable","filtro","filter","clamp","stand","cstand","c-stand","dolly",
    "riel","carro","movilux","follow","focus","steadicam","ronin",
    "memoria","tarjeta","sd","cf","cfexpress","reader","lector","disco",
    "kit","pack","combo","de","del","con","y","la","el","para","o","u",
    "el","la","los","las","un","una","unos","unas","mts","cm","mm",
    "watts","w","watt","x","plus","new","ii","iii","iv","v","vi","vii","viii",
    "promo","oferta","unidad","unidades","und","u","items",
}

# Mapeo de estado Booqable → estado local
def map_status(booqable_status: str, payment_status: str | None) -> str:
    s = (booqable_status or "").strip().lower()
    p = (payment_status or "").strip().lower()
    if s == "canceled":
        return "cancelado"
    if s == "stopped":
        return "finalizado" if p == "paid" else "devuelto"
    if s == "started":
        return "retirado"
    if s == "reserved":
        return "confirmado"
    if s in ("new", "draft"):
        return "presupuesto"
    return "presupuesto"


# Ajuste a planilla: cuando el monto REAL cobrado (de --montos-reales) es
# MENOR al grand_total de Booqable, aplicamos un descuento_pct al pedido para
# llegar al cobrado. Pasa con clientes que en Booqable se cargaban a precio
# lista (ej. Filmar, escuela) pero pagaban menos por un descuento off-system.
# Se aplica POR PEDIDO (solo los que difieren hacia abajo), no por cliente.
# Umbral minimo de descuento para evitar ruido de redondeo.
AJUSTE_PLANILLA_UMBRAL_PCT = 1.0


def _parse_money(s: str) -> float:
    s = (s or "").replace("$", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def slugify(text: str, max_len: int = 80) -> str:
    if not text:
        return ""
    n = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9]+", "-", n)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:max_len].rstrip("-")


def cents_to_ars(cents: str | int | None) -> int:
    if cents is None or cents == "":
        return 0
    try:
        return int(int(cents) / 100)
    except (ValueError, TypeError):
        return 0


def iso_date(iso_dt: str | None) -> str:
    """Booqable usa '2026-05-22T15:33:33.432008+00:00'. Local espera 'YYYY-MM-DD'."""
    if not iso_dt:
        return ""
    return iso_dt[:10]


# ─────────────────────────────────────────────────────────────────────────────
# Carga + indices
# ─────────────────────────────────────────────────────────────────────────────

def load_data(args):
    with open(args.orders, encoding="utf-8") as f:
        orders = list(csv.DictReader(f))
    with open(args.lines, encoding="utf-8") as f:
        lines = list(csv.DictReader(f))
    with open(args.products, encoding="utf-8") as f:
        products = list(csv.DictReader(f))
    with open(args.customers, encoding="utf-8") as f:
        customers = list(csv.DictReader(f))
    # Fallback de clientes: si --customers es una lista curada (subset), puede
    # faltar algun cliente que SI tiene pedidos. Los recuperamos de este CSV
    # crudo. Solo se agregan los referenciados por pedidos importables.
    if args.customers_fallback:
        with open(args.customers_fallback, encoding="utf-8") as f:
            fallback = list(csv.DictReader(f))
        curated_ids = {c["id"] for c in customers}
        order_cust_ids = {
            o.get("customer_id") for o in orders
            if o.get("status") in ("stopped", "started", "reserved")
        }
        recovered = [
            c for c in fallback
            if c["id"] not in curated_ids and c["id"] in order_cust_ids
        ]
        if recovered:
            print(f"  + {len(recovered)} clientes recuperados del fallback "
                  f"(faltaban en la lista curada pero tienen pedidos)", file=sys.stderr)
            customers = customers + recovered
    equipos = json.load(open(args.equipos, encoding="utf-8"))
    documents = []
    if args.documents:
        with open(args.documents, encoding="utf-8") as f:
            documents = list(csv.DictReader(f))
    plannings = []
    if args.plannings:
        with open(args.plannings, encoding="utf-8") as f:
            plannings = list(csv.DictReader(f))
    # montos reales (planilla): remito → monto cobrado en pesos. Para clientes
    # con descuento off-Booqable (CLIENTES_MONTO_REAL). Columnas: Remito N° (2),
    # Monto (6). Sumamos por remito (varias lineas por pedido).
    real_monto_by_remito = {}
    if getattr(args, "montos_reales", None):
        with open(args.montos_reales, encoding="utf-8") as f:
            rr = csv.reader(f)
            next(rr, None)
            for row in rr:
                if len(row) < 7:
                    continue
                rem = (row[2] or "").strip()
                if rem:
                    real_monto_by_remito[rem] = real_monto_by_remito.get(rem, 0) + _parse_money(row[6])
    return orders, lines, products, customers, equipos, documents, plannings, real_monto_by_remito


def _tokens(text: str) -> set[str]:
    if not text:
        return set()
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return {x for x in set(t.split()) - STOP_TOKENS if len(x) > 1}


def build_indices(orders, lines, products, customers, equipos, documents=None, plannings=None):
    documents = documents or []
    plannings = plannings or []
    # customer_id (UUID) → datos. Genera email placeholder determinista si el
    # cliente no tiene email (Booqable lo permite, nuestra DB exige email
    # NOT NULL UNIQUE). Asi no se pierden los pedidos de esos clientes.
    cust_by_id = {}
    for c in customers:
        email = (c.get("email") or "").strip().lower()
        placeholder = False
        if not email:
            email = f"sin-email-{c['id'][:8]}@booqable.local"
            placeholder = True
        cust_by_id[c["id"]] = {
            "email": email,
            "email_placeholder": placeholder,
            "name": c.get("name", ""),
            "telefono": _extract_prop(c.get("properties"), "telefono"),
        }

    # product_id (UUID) → product dict
    prod_by_id = {p["id"]: p for p in products}

    # local equipos slug set (para verificar que los mappings existen)
    local_slugs = {e["slug"] for e in equipos if e.get("slug")}

    # local equipos: slug → token set (para fuzzy matching)
    local_tokens = []
    for e in equipos:
        slug = e.get("slug")
        if not slug:
            continue
        toks = _tokens(" ".join([
            e.get("nombre") or "", e.get("marca") or "",
            e.get("modelo") or "", slug.replace("-", " "),
        ]))
        if toks:
            local_tokens.append((slug, toks))

    # lines: parent_id → children
    children_by_parent = {}
    parent_ids_with_kids = set()
    for l in lines:
        pid = l.get("parent_line_id")
        if pid:
            children_by_parent.setdefault(pid, []).append(l)
            parent_ids_with_kids.add(pid)

    # lines por order_id (solo charge + owner=orders)
    lines_by_order = {}
    for l in lines:
        if l.get("owner_type") != "orders" or l.get("line_type") != "charge":
            continue
        oid = l.get("order_id")
        if oid:
            lines_by_order.setdefault(oid, []).append(l)

    # ── Fallback via documentos (facturas) ──────────────────────────────────
    # Algunos pedidos no tienen order-lines pero si document-lines (la factura
    # conserva el detalle). Construimos order_id → mejor documento → sus
    # charge-lines, para usarlas cuando faltan las order-lines.
    doclines_by_owner = {}  # document_id → [charge lines]
    for l in lines:
        if l.get("owner_type") != "documents" or l.get("line_type") != "charge":
            continue
        oid = l.get("owner_id")
        if oid:
            doclines_by_owner.setdefault(oid, []).append(l)

    # order_id → documentos (con su conteo de lineas). Preferimos el doc con
    # MAS charge-lines (el que tiene el detalle real), evitando double-count
    # al elegir uno solo por pedido.
    docs_by_order = {}
    for d in documents:
        oid = d.get("order_id")
        if oid:
            docs_by_order.setdefault(oid, []).append(d)

    doclines_by_order = {}  # order_id → [charge lines del mejor documento]
    for oid, docs in docs_by_order.items():
        best_lines = []
        best_precio = -1
        for d in docs:
            dl = doclines_by_owner.get(d["id"], [])
            # Elegir por mayor suma de precios, NO por cantidad de lineas:
            # un quote puede tener mas lineas pero con precio 0, mientras la
            # factura tiene los precios reales.
            precio = sum(int(l.get("price_in_cents") or 0) for l in dl)
            if precio > best_precio:
                best_precio = precio
                best_lines = dl
        # Solo usar doc-lines si tienen precios reales; si no, dejamos que
        # caiga al fallback de plannings.
        if best_lines and best_precio > 0:
            doclines_by_order[oid] = best_lines

    # ── Fallback via plannings (reserva de stock) ───────────────────────────
    # Ultimo recurso: pedidos sin order-lines ni doc-lines pero con plannings
    # (reserva fisica). Las plannings tienen item_id + quantity pero NO precio,
    # asi que sintetizamos pseudo-lineas con peso = base_price del producto *
    # cantidad (o solo cantidad si no hay precio). El grand_total del pedido se
    # distribuye proporcional a ese peso, igual que las lineas reales.
    plan_pseudolines_by_order = {}
    for p in plannings:
        item_id = p.get("item_id")
        oid = p.get("order_id")
        if not item_id or not oid:
            continue
        try:
            qty = max(1, int(p.get("quantity") or "1"))
        except ValueError:
            qty = 1
        prod = prod_by_id.get(item_id)
        base = int((prod or {}).get("base_price_in_cents") or 0)
        peso_cents = (base * qty) if base > 0 else (10000 * qty)  # fallback peso neutral
        plan_pseudolines_by_order.setdefault(oid, []).append({
            "id": f"planning:{p.get('id','')}",
            "item_id": item_id,
            "title": (prod or {}).get("name", ""),
            "quantity": str(qty),
            "price_in_cents": str(peso_cents),
            "price_each_in_cents": str(base if base > 0 else peso_cents),
            "owner_type": "orders",
            "line_type": "charge",
        })

    return {
        "cust_by_id": cust_by_id,
        "prod_by_id": prod_by_id,
        "local_slugs": local_slugs,
        "local_tokens": local_tokens,
        "lines_by_order": lines_by_order,
        "doclines_by_order": doclines_by_order,
        "planlines_by_order": plan_pseudolines_by_order,
        "parent_ids_with_kids": parent_ids_with_kids,
    }


def _best_token_match(text: str, idx: dict) -> tuple[str | None, float]:
    """Devuelve (local_slug, score) o (None, 0) si no hay match decente."""
    btoks = _tokens(text)
    if not btoks:
        return None, 0.0
    best_slug, best_score = None, 0.0
    for slug, ltoks in idx["local_tokens"]:
        inter = btoks & ltoks
        if not inter:
            continue
        # overlap coefficient = |A ∩ B| / min(|A|, |B|)
        score = len(inter) / min(len(btoks), len(ltoks))
        if score > best_score:
            best_score = score
            best_slug = slug
    return best_slug, best_score


def _extract_prop(raw_json: str | None, key: str) -> str:
    if not raw_json:
        return ""
    try:
        d = json.loads(raw_json)
        return str(d.get(key, "")).strip() if isinstance(d, dict) else ""
    except json.JSONDecodeError:
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# Resolucion de equipo_slug para una linea
# ─────────────────────────────────────────────────────────────────────────────

def resolve_equipo(
    line: dict,
    idx: dict,
    placeholders: dict,
) -> tuple[str | None, int]:
    """Devuelve (equipo_slug, qty_multiplier) o (None, 1) si la linea debe
    saltarse. Actualiza `placeholders` in-place con nuevos placeholders."""
    item_id = line.get("item_id")
    prod = idx["prod_by_id"].get(item_id) if item_id else None
    title = (line.get("title") or "").strip()

    # 1. Producto activo en Booqable
    if prod:
        bslug = (prod.get("slug") or "").strip().lower()
        # 1a. Mapping explicito
        if bslug in MAPPING_BY_BOOQABLE_SLUG:
            return MAPPING_BY_BOOQABLE_SLUG[bslug]
        # 1b. Placeholder explicito
        if bslug in EXPLICIT_PLACEHOLDERS:
            return _ensure_placeholder(prod, placeholders, by_slug=bslug), 1
        # 1c. Slug coincide con local
        if bslug in idx["local_slugs"]:
            return bslug, 1
        # 1d. Fuzzy: token-overlap contra el catalogo local
        combined = " ".join([prod.get("name") or "", prod.get("sku") or "", bslug.replace("-", " ")])
        match, score = _best_token_match(combined, idx)
        if match and score >= TOKEN_OVERLAP_THRESHOLD:
            return match, 1
        # 1e. Fallback: placeholder
        return _ensure_placeholder(prod, placeholders, by_slug=bslug), 1

    # 2. Linea archived (item_id no esta en products.csv) — usar el title
    if title in MAPPING_BY_LINE_TITLE:
        return MAPPING_BY_LINE_TITLE[title]
    if title in PLACEHOLDER_BY_TITLE:
        return _ensure_placeholder_by_title(title, placeholders), 1
    if not title:
        return None, 1  # linea sin title ni item_id, saltar

    # 2b. Fuzzy token-overlap por title
    match, score = _best_token_match(title, idx)
    if match and score >= TOKEN_OVERLAP_THRESHOLD:
        return match, 1

    # 3. Linea archived sin mapping → placeholder por titulo
    return _ensure_placeholder_by_title(title, placeholders), 1


def _ensure_placeholder(prod: dict, placeholders: dict, by_slug: str) -> str:
    """Crea (o reutiliza) un placeholder a partir de un product activo."""
    key = f"by-bslug:{by_slug}"
    if key in placeholders:
        return placeholders[key]["slug"]
    nombre = prod.get("name") or by_slug or "placeholder"
    local_slug = slugify(f"booqable-{by_slug}")[:80]
    placeholders[key] = {
        "slug": local_slug,
        "nombre": nombre,
        "marca": "",
        "modelo": "",
        "source_booqable_slug": by_slug,
        "source_booqable_id": prod.get("id", ""),
        "precio_referencia_ars": cents_to_ars(prod.get("base_price_in_cents")),
    }
    return local_slug


def _ensure_placeholder_by_title(title: str, placeholders: dict) -> str:
    key = f"by-title:{title.lower()}"
    if key in placeholders:
        return placeholders[key]["slug"]
    local_slug = slugify(f"booqable-{title}")[:80]
    placeholders[key] = {
        "slug": local_slug,
        "nombre": title,
        "marca": "",
        "modelo": "",
        "source_booqable_slug": "",
        "source_booqable_id": "",
        "precio_referencia_ars": 0,
    }
    return local_slug


# ─────────────────────────────────────────────────────────────────────────────
# Build clientes (TODOS, para wipe-and-reimport limpio)
# ─────────────────────────────────────────────────────────────────────────────

def build_clientes(customers, idx):
    """Convierte TODOS los customers de Booqable a clientes locales.

    Email placeholder para los que no tienen (mismo esquema que cust_by_id).
    Dedup por email (case-insensitive) — si dos customers comparten email,
    gana el primero. Devuelve lista lista para import_clientes.
    """
    out = []
    seen = set()
    for c in customers:
        cinfo = idx["cust_by_id"].get(c["id"])
        if not cinfo:
            continue
        email = cinfo["email"]
        if email.lower() in seen:
            continue
        seen.add(email.lower())

        name = (c.get("name") or "").strip()
        parts = name.split()
        nombre = parts[0] if parts else email.split("@")[0]
        apellido = " ".join(parts[1:]) if len(parts) > 1 else "-"

        props_raw = c.get("properties") or ""
        telefono = _extract_prop(props_raw, "telefono")
        direccion = _extract_prop(props_raw, "direccion_principal")
        cuit = _extract_prop(props_raw, "cuil_cuit")

        try:
            descuento = float(c.get("discount_percentage") or "0")
        except ValueError:
            descuento = 0.0
        is_commercial = (c.get("legal_type") or "").strip().lower() == "commercial"

        cliente = {
            "email": email,
            "nombre": nombre,
            "apellido": apellido,
            "telefono": telefono,
            "direccion": direccion,
            "cuit": cuit,
            "descuento": descuento,
            "perfil_impuestos": "responsable_inscripto" if is_commercial else "consumidor_final",
        }
        if is_commercial:
            cliente["razon_social"] = name
        num = (c.get("number") or "").strip()
        notas = []
        if num:
            notas.append(f"Booqable #{num}")
        if cinfo.get("email_placeholder"):
            notas.append("sin email en Booqable (placeholder)")
        if notas:
            cliente["notas"] = " — ".join(notas)
        out.append(cliente)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Build alquileres
# ─────────────────────────────────────────────────────────────────────────────

SIN_DETALLE_SLUG = "booqable-pedido-sin-detalle"
SIN_DETALLE_NOMBRE = "Pedido histórico (sin detalle de items)"


def _jornadas_local(fecha_desde: str, fecha_hasta: str) -> int:
    """Replica el calculo del frontend (jornadasEntre en usePedidoDraft.ts):
    dias de diferencia + 1 (inclusivo). Asi precio_jornada * jornadas en el
    display coincide con lo que asignamos."""
    import datetime as _dt
    try:
        d0 = _dt.date.fromisoformat(fecha_desde)
        d1 = _dt.date.fromisoformat(fecha_hasta)
    except (ValueError, TypeError):
        return 1
    diff = (d1 - d0).days
    if diff < 0:
        return 1
    return max(1, diff + 1)


def build_alquileres(orders, idx):
    placeholders: dict[str, dict] = {}
    alquileres: list[dict] = []
    skipped: list[dict] = []
    clientes_sin_email: dict[str, dict] = {}
    usa_sin_detalle = False

    # Ordenar por numero_pedido Booqable ASC = orden cronologico.
    # El numero_pedido local se reasigna 1..N (secuencial sin gaps de los
    # cancelados). El numero original Booqable se preserva en notas.
    def _num(o):
        try: return int(o.get("number") or "0")
        except ValueError: return 0
    orders = sorted(orders, key=_num)

    for o in orders:
        status = (o.get("status") or "").strip().lower()
        if status not in STATUSES_TO_IMPORT:
            skipped.append({
                "numero": o.get("number", ""),
                "status": status,
                "motivo": f"status='{status}' no en {sorted(STATUSES_TO_IMPORT)}",
            })
            continue

        cust = idx["cust_by_id"].get(o.get("customer_id") or "")
        if not cust:
            skipped.append({
                "numero": o.get("number", ""),
                "status": status,
                "motivo": "customer_id no existe en customers.csv",
            })
            continue

        fecha_desde = iso_date(o.get("starts_at"))
        fecha_hasta = iso_date(o.get("stops_at"))
        jornadas = _jornadas_local(fecha_desde, fecha_hasta)

        # Montos de Booqable:
        #   - price_in_cents = BRUTO (lista, antes del descuento del pedido)
        #   - grand_total_with_tax = NETO (despues del descuento de Booqable)
        # Distribuimos el BRUTO entre los items (precios lista) y aplicamos un
        # descuento_pct para llegar al neto. Asi NO se descuenta sobre un monto
        # ya descontado (bug: pedidos con descuento en Booqable quedaban con
        # los items ya bajados y encima se les aplicaba otro descuento).
        grand_total = cents_to_ars(
            o.get("grand_total_with_tax_in_cents") or o.get("grand_total_in_cents")
        )
        bruto = cents_to_ars(o.get("price_in_cents"))
        # Si no hay bruto (pedidos viejos) o es menor al neto, usamos el neto
        # como bruto (descuento 0).
        if bruto < grand_total:
            bruto = grand_total

        # ── Paso 1: componer items mergeando PLANNINGS + charge-lines ───────
        # Los `lines` (charge) exportados de Booqable son INCOMPLETOS para
        # varios pedidos (ej. #507 tiene 4 productos pero solo 1 charge-line).
        # Los PLANNINGS (reservas fisicas) siempre reflejan los productos
        # trackeados reservados (== item_count), asi que son la fuente
        # confiable de composicion. Las charge-lines aportan: (a) items
        # custom/no-trackeados sin planning (ej. "Sopapa"), (b) hints de
        # precio. Mergeamos dedupeando por item_id para no doble-contar.
        #
        # Peso para distribuir el grand_total: base_price del producto (para
        # plannings) o price_in (para charge-lines). El grand_total real
        # absorbe descuentos, asi que sum(subtotales) == lo que se cobro.
        plan_lines = idx.get("planlines_by_order", {}).get(o["id"], [])
        charge_lines = idx["lines_by_order"].get(o["id"], [])
        if not charge_lines:
            charge_lines = idx.get("doclines_by_order", {}).get(o["id"], [])
        charge_lines = [
            l for l in charge_lines if l["id"] not in idx["parent_ids_with_kids"]
        ]

        by_slug: dict[str, dict] = {}
        covered_item_ids: set[str] = set()

        # (a) Plannings → composicion confiable (peso = base_price * qty).
        for pl in plan_lines:
            item_id = pl.get("item_id")
            try:
                cantidad = max(1, int(pl.get("quantity") or "1"))
            except ValueError:
                cantidad = 1
            peso = cents_to_ars(pl.get("price_in_cents")) or 1  # base_price*qty
            equipo_slug, qty_mult = resolve_equipo(pl, idx, placeholders)
            if equipo_slug is None:
                continue
            if item_id:
                covered_item_ids.add(item_id)
            cantidad *= qty_mult
            agg = by_slug.setdefault(equipo_slug, {"cantidad": 0, "peso": 0})
            agg["cantidad"] += cantidad
            agg["peso"] += peso

        # (b) Charge-lines → items sin planning (custom/no-trackeados). Las que
        # duplican un planning (mismo item_id) se saltan: evita doble-conteo.
        for l in charge_lines:
            item_id = l.get("item_id")
            if item_id and item_id in covered_item_ids:
                continue  # ya cubierto por un planning
            price_in = cents_to_ars(l.get("price_in_cents"))
            es_hijo_combo = bool(l.get("parent_line_id"))
            try:
                cantidad = max(1, int(l.get("quantity") or "1"))
            except ValueError:
                cantidad = 1
            if price_in > 0:
                peso = price_in
            elif es_hijo_combo:
                prod = idx["prod_by_id"].get(item_id)
                base = cents_to_ars((prod or {}).get("base_price_in_cents"))
                peso = (base * cantidad) if base > 0 else 1
            else:
                continue  # standalone sin precio → free accessory
            equipo_slug, qty_mult = resolve_equipo(l, idx, placeholders)
            if equipo_slug is None:
                continue
            cantidad *= qty_mult
            agg = by_slug.setdefault(equipo_slug, {"cantidad": 0, "peso": 0})
            agg["cantidad"] += cantidad
            agg["peso"] += peso

        # ── Paso 2: distribuir el BRUTO proporcional al peso ────────────────
        # Items quedan a precio LISTA (sum(subtotal) == bruto). El descuento del
        # pedido (Booqable y/o off-system) se aplica via descuento_pct, no
        # bajando los items. Asi nunca se descuenta sobre un monto ya neteado.
        items = []
        peso_total = sum(a["peso"] for a in by_slug.values())
        if by_slug and peso_total > 0:
            asignado_acc = 0
            slugs = list(by_slug.items())
            for i, (slug, agg) in enumerate(slugs):
                if i == len(slugs) - 1:
                    # ultimo item absorbe el redondeo para cuadrar exacto
                    asignado = bruto - asignado_acc
                else:
                    asignado = round(bruto * agg["peso"] / peso_total)
                    asignado_acc += asignado
                cantidad = agg["cantidad"]
                precio_jornada = round(asignado / (cantidad * jornadas)) if (cantidad and jornadas) else asignado
                items.append({
                    "equipo_slug": slug,
                    "cantidad": cantidad,
                    "precio_jornada": precio_jornada,
                    "subtotal": asignado,
                })
        elif bruto > 0:
            # Pedido con monto pero sin lineas en el CSV de Booqable (export
            # incompleto). Creamos 1 item sintetico a un placeholder generico
            # para que el pedido no quede vacio y el total se muestre bien.
            usa_sin_detalle = True
            precio_jornada = round(bruto / jornadas) if jornadas else bruto
            items.append({
                "equipo_slug": SIN_DETALLE_SLUG,
                "cantidad": 1,
                "precio_jornada": precio_jornada,
                "subtotal": bruto,
            })

        # Numero local secuencial 1..N. Numero original Booqable se guarda en notas.
        numero_pedido = len(alquileres) + 1
        booqable_num = (o.get("number") or "").strip()

        # Snapshot denormalizado del cliente
        name_parts = (cust["name"] or "").strip().split()
        cliente_nombre = name_parts[0] if name_parts else cust["email"].split("@")[0]
        if len(name_parts) > 1:
            cliente_nombre = " ".join(name_parts)

        # Trackear clientes con email placeholder para emitirlos en clientes.json
        # (no estaban en el import original porque no tenian email).
        if cust.get("email_placeholder"):
            clientes_sin_email[cust["email"]] = {
                "email": cust["email"],
                "nombre": name_parts[0] if name_parts else cliente_nombre,
                "apellido": " ".join(name_parts[1:]) if len(name_parts) > 1 else "-",
                "telefono": cust.get("telefono") or "",
                "direccion": "",
                "cuit": "",
                "notas": "Cliente sin email en Booqable (email placeholder generado)",
            }

        # Monto/descuento — UN solo descuento efectivo sobre el BRUTO.
        #   real = lo realmente cobrado:
        #     - default: grand_total de Booqable (neto, ya con el descuento
        #       del pedido si lo tenia; Booqable lo marca como pagado).
        #     - si el pedido NO tiene descuento en Booqable (bruto==grand) y la
        #       planilla registro un monto menor → descuento off-system real
        #       (ej. Filmar). Usamos la planilla.
        #   No aplicamos planilla cuando el pedido YA tiene descuento en
        #   Booqable: ese descuento es el real, y una planilla menor suele ser
        #   un error de carga (no doble-descontar).
        real = grand_total
        tiene_desc_booqable = bruto > grand_total + 1
        real_montos = idx.get("real_monto_by_remito", {})
        if (not tiene_desc_booqable
                and booqable_num in real_montos
                and bruto > 0):
            planilla = round(real_montos[booqable_num])
            disc_planilla = round((1 - planilla / bruto) * 100, 2)
            if 0 < planilla < bruto and disc_planilla >= AJUSTE_PLANILLA_UMBRAL_PCT:
                real = planilla

        descuento_pct = round((1 - real / bruto) * 100, 2) if bruto > 0 else 0.0
        if descuento_pct < 0:
            descuento_pct = 0.0
        monto_total = real

        alq = {
            "numero_pedido": numero_pedido,
            "cliente_email": cust["email"],
            "cliente_nombre": cliente_nombre,
            "cliente_telefono": cust.get("telefono") or None,
            "estado": map_status(status, o.get("payment_status")),
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "monto_total": monto_total,
            "monto_pagado": cents_to_ars(o.get("amount_paid_in_cents")),
            "descuento_pct": descuento_pct,
            "fuente": "booqable-historico",
            "notas": f"Booqable #{booqable_num} (imported)" if booqable_num else "Booqable (imported)",
            "items": items,
            "pagos": [],
        }
        alquileres.append(alq)

    placeholder_list = list(placeholders.values())
    if usa_sin_detalle:
        placeholder_list.append({
            "slug": SIN_DETALLE_SLUG,
            "nombre": SIN_DETALLE_NOMBRE,
            "marca": "",
            "modelo": "",
            "source_booqable_slug": "",
            "source_booqable_id": "",
            "precio_referencia_ars": 0,
        })

    return alquileres, placeholder_list, skipped, list(clientes_sin_email.values())


# ─────────────────────────────────────────────────────────────────────────────
# Output
# ─────────────────────────────────────────────────────────────────────────────

def write_outputs(out_dir: Path, alquileres, placeholders, skipped, idx, clientes_extra=None):
    out_dir.mkdir(parents=True, exist_ok=True)
    clientes_extra = clientes_extra or []

    # alquileres.json
    alq_path = out_dir / "alquileres.json"
    alq_path.write_text(
        json.dumps(alquileres, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # clientes.json: solo los clientes sin email (con placeholder generado).
    # Los demas ya fueron importados en el paso de clientes. Idempotente:
    # el importer upsertea por email.
    clientes_path = out_dir / "clientes.json"
    clientes_path.write_text(
        json.dumps(clientes_extra, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # placeholders.json (humano-legible para debug)
    ph_path = out_dir / "placeholders.json"
    ph_path.write_text(
        json.dumps(placeholders, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # placeholders_equipos.json: formato consumido por el endpoint
    # /admin/dataio/import (auto-crea equipos historicos antes de alquileres).
    # Solo slug + nombre (los otros campos default a historico/0/0).
    ph_equipos = [{"slug": p["slug"], "nombre": p["nombre"]} for p in placeholders]
    ph_equipos_path = out_dir / "placeholders_equipos.json"
    ph_equipos_path.write_text(
        json.dumps(ph_equipos, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # ZIP: clientes + alquileres + placeholders_equipos juntos. El endpoint
    # reconoce los 3 archivos automaticamente — el operador solo sube ESTE zip.
    # IMPORTANTE: clientes va primero (FK de alquileres) pero el orchestrator
    # ya respeta el orden OPERATIONAL_ENTITIES (clientes -> alquileres).
    zip_path = out_dir / "alquileres.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        if clientes_extra:
            zf.write(clientes_path, arcname="clientes.json")
        zf.write(alq_path, arcname="alquileres.json")
        zf.write(ph_equipos_path, arcname="placeholders_equipos.json")

    # placeholders.sql (para pegar en Railway DB UI ANTES del import)
    sql_lines = [
        "-- Placeholders historicos para items rentados en Booqable sin",
        "-- equivalente en el catalogo local. Idempotente: skip si ya existen.",
        "-- estado='historico', visible_catalogo=0, cantidad=0",
        "",
    ]
    for p in placeholders:
        nombre_esc = p["nombre"].replace("'", "''")
        sql_lines.append(
            f"INSERT INTO equipos (slug, nombre, cantidad, visible_catalogo, estado) "
            f"VALUES ('{p['slug']}', '{nombre_esc}', 0, 0, 'historico') "
            f"ON CONFLICT (slug) DO NOTHING;"
        )
    sql_path = out_dir / "placeholders.sql"
    sql_path.write_text("\n".join(sql_lines) + "\n", encoding="utf-8")

    # post_import.sql (correr DESPUES de subir el zip)
    max_num = max((a["numero_pedido"] for a in alquileres if a["numero_pedido"]), default=0)
    post_sql = [
        "-- Correr DESPUES de subir alquileres.zip a /admin/dataio/import.",
        "-- Bumpea numero_pedido_seq para que las nuevas ordenes manuales no",
        "-- colisionen con los numeros importados (1.." + str(max_num) + ").",
        "",
        f"SELECT setval('numero_pedido_seq', {max_num}, true);",
        "",
        "-- Tambien bumpea alquileres_id_seq y alquiler_items_id_seq por si",
        "-- hubo inserts directos via SQL antes (defensivo, idempotente).",
        "SELECT setval('alquileres_id_seq', GREATEST(1, (SELECT COALESCE(MAX(id), 0) FROM alquileres)), true);",
        "SELECT setval('alquiler_items_id_seq', GREATEST(1, (SELECT COALESCE(MAX(id), 0) FROM alquiler_items)), true);",
    ]
    (out_dir / "post_import.sql").write_text("\n".join(post_sql) + "\n", encoding="utf-8")

    # skipped.csv
    if skipped:
        skip_path = out_dir / "skipped.csv"
        with skip_path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["numero", "status", "motivo"])
            w.writeheader()
            w.writerows(skipped)

    # report.txt
    total_items = sum(len(a["items"]) for a in alquileres)
    unmapped_to_local = sum(
        1 for a in alquileres for it in a["items"]
        if it["equipo_slug"] not in idx["local_slugs"]
    )
    items_mapped_to_local = total_items - unmapped_to_local
    report = [
        f"=== Booqable → alquileres import ===",
        f"",
        f"Alquileres a importar:       {len(alquileres)}",
        f"  con items > 0:             {sum(1 for a in alquileres if a['items'])}",
        f"  sin items (warning):       {sum(1 for a in alquileres if not a['items'])}",
        f"Items totales:               {total_items}",
        f"  a equipos del catalogo:    {items_mapped_to_local}",
        f"  a placeholders:            {unmapped_to_local}",
        f"Placeholders nuevos:         {len(placeholders)}",
        f"Pedidos saltados:            {len(skipped)}",
        f"",
        f"=== Pasos para importar (UN SOLO PASO) ===",
        f"  - Andar a /admin/dataio en la web",
        f"  - Subir alquileres.zip en la seccion 'Import operacional'",
        f"  - El endpoint crea los {len(placeholders)} placeholders solo y bumpea",
        f"    las secuencias automaticamente. No hace falta tocar SQL.",
        f"",
        f"  (Los archivos placeholders.sql y post_import.sql que siguen abajo",
        f"  son backup por si la version del backend deployada todavia no soporta",
        f"  el flujo all-in-one — verificar fecha de deploy >= hoy)",
        f"",
    ]
    (out_dir / "report.txt").write_text("\n".join(report), encoding="utf-8")

    return {
        "alquileres": len(alquileres),
        "items_total": total_items,
        "items_to_local": items_mapped_to_local,
        "items_to_placeholder": unmapped_to_local,
        "placeholders": len(placeholders),
        "skipped": len(skipped),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--orders", required=True)
    ap.add_argument("--lines", required=True)
    ap.add_argument("--products", required=True)
    ap.add_argument("--customers", required=True,
                    help="CSV de clientes (puede ser tu lista curada)")
    ap.add_argument("--customers-fallback", default=None,
                    help="CSV crudo de clientes; recupera los que faltan en "
                         "--customers pero tienen pedidos")
    ap.add_argument("--equipos", required=True)
    ap.add_argument("--documents", default=None,
                    help="documents.csv (facturas) opcional, para recuperar "
                         "detalle de pedidos sin order-lines")
    ap.add_argument("--plannings", default=None,
                    help="plannings.csv (reservas) opcional, ultimo fallback "
                         "para pedidos sin order-lines ni doc-lines")
    ap.add_argument("--montos-reales", default=None,
                    help="CSV planilla (Rental Historicos) con remito+monto real "
                         "cobrado; para clientes con descuento off-Booqable")
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()

    orders, lines, products, customers, equipos, documents, plannings, real_montos = load_data(args)
    print(f"orders: {len(orders)}, lines: {len(lines)}, products: {len(products)}, "
          f"customers: {len(customers)}, equipos locales: {len(equipos)}, "
          f"documents: {len(documents)}, plannings: {len(plannings)}, "
          f"montos_reales: {len(real_montos)}", file=sys.stderr)

    idx = build_indices(orders, lines, products, customers, equipos, documents, plannings)
    idx["real_monto_by_remito"] = real_montos
    alquileres, placeholders, skipped, clientes_sin_email = build_alquileres(orders, idx)
    # clientes.json incluye TODOS (para wipe-and-reimport limpio), no solo los
    # sin email. El importer upsertea por email asi que es idempotente.
    clientes_all = build_clientes(customers, idx)
    stats = write_outputs(Path(args.outdir), alquileres, placeholders, skipped, idx, clientes_all)
    stats["clientes_total"] = len(clientes_all)
    stats["clientes_sin_email"] = len(clientes_sin_email)

    print(f"\nResumen:", file=sys.stderr)
    for k, v in stats.items():
        print(f"  {k:>20}: {v}", file=sys.stderr)
    print(f"\nOutput: {args.outdir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
