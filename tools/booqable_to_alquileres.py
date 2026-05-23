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
    equipos = json.load(open(args.equipos, encoding="utf-8"))
    return orders, lines, products, customers, equipos


def _tokens(text: str) -> set[str]:
    if not text:
        return set()
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return {x for x in set(t.split()) - STOP_TOKENS if len(x) > 1}


def build_indices(orders, lines, products, customers, equipos):
    # customer_id (UUID) → email
    cust_by_id = {}
    for c in customers:
        email = (c.get("email") or "").strip().lower()
        if email:
            cust_by_id[c["id"]] = {
                "email": email,
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

    return {
        "cust_by_id": cust_by_id,
        "prod_by_id": prod_by_id,
        "local_slugs": local_slugs,
        "local_tokens": local_tokens,
        "lines_by_order": lines_by_order,
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
# Build alquileres
# ─────────────────────────────────────────────────────────────────────────────

def build_alquileres(orders, idx):
    placeholders: dict[str, dict] = {}
    alquileres: list[dict] = []
    skipped: list[dict] = []

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
                "motivo": "customer_id sin match en customers.csv (sin email)",
            })
            continue

        # Filtrar lineas: ignorar combo parents (los children tienen la
        # composicion real). Quedarse con children + simples.
        all_lines = idx["lines_by_order"].get(o["id"], [])
        useful_lines = [
            l for l in all_lines
            if l["id"] not in idx["parent_ids_with_kids"]
        ]

        items = []
        for l in useful_lines:
            equipo_slug, qty_mult = resolve_equipo(l, idx, placeholders)
            if equipo_slug is None:
                continue
            try:
                cantidad = max(1, int(l.get("quantity") or "1"))
            except ValueError:
                cantidad = 1
            cantidad *= qty_mult
            precio_each_ars = cents_to_ars(l.get("price_each_in_cents"))
            subtotal_ars = cents_to_ars(l.get("price_in_cents"))
            if qty_mult > 1:
                # Si expandimos un kit, el precio unitario baja proporcionalmente
                precio_each_ars = precio_each_ars // qty_mult if precio_each_ars else 0
            items.append({
                "equipo_slug": equipo_slug,
                "cantidad": cantidad,
                "precio_jornada": precio_each_ars,
                "subtotal": subtotal_ars,
            })

        try:
            numero_pedido = int(o.get("number") or "0")
        except ValueError:
            numero_pedido = 0

        # Snapshot denormalizado del cliente
        name_parts = (cust["name"] or "").strip().split()
        cliente_nombre = name_parts[0] if name_parts else cust["email"].split("@")[0]
        if len(name_parts) > 1:
            cliente_nombre = " ".join(name_parts)

        # Descuento explicito si Booqable lo tiene
        try:
            descuento_pct = float(o.get("discount_percentage") or "0")
        except ValueError:
            descuento_pct = 0.0

        alq = {
            "numero_pedido": numero_pedido,
            "cliente_email": cust["email"],
            "cliente_nombre": cliente_nombre,
            "cliente_telefono": cust.get("telefono") or None,
            "estado": map_status(status, o.get("payment_status")),
            "fecha_desde": iso_date(o.get("starts_at")),
            "fecha_hasta": iso_date(o.get("stops_at")),
            "monto_total": cents_to_ars(o.get("grand_total_with_tax_in_cents") or o.get("grand_total_in_cents")),
            "monto_pagado": cents_to_ars(o.get("amount_paid_in_cents")),
            "descuento_pct": descuento_pct,
            "fuente": "booqable-historico",
            "notas": f"Booqable #{o.get('number', '')} (imported)",
            "items": items,
            "pagos": [],
        }
        alquileres.append(alq)

    return alquileres, list(placeholders.values()), skipped


# ─────────────────────────────────────────────────────────────────────────────
# Output
# ─────────────────────────────────────────────────────────────────────────────

def write_outputs(out_dir: Path, alquileres, placeholders, skipped, idx):
    out_dir.mkdir(parents=True, exist_ok=True)

    # alquileres.json + zip
    alq_path = out_dir / "alquileres.json"
    alq_path.write_text(
        json.dumps(alquileres, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    zip_path = out_dir / "alquileres.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(alq_path, arcname="alquileres.json")

    # placeholders.json
    ph_path = out_dir / "placeholders.json"
    ph_path.write_text(
        json.dumps(placeholders, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

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
        f"=== Pasos para importar ===",
        f"1. Crear placeholders (Railway DB UI):",
        f"   - Abri la query box en Postgres",
        f"   - Pega el contenido de placeholders.sql",
        f"   - Ejecutar",
        f"",
        f"2. Import operacional (admin UI):",
        f"   - /admin/dataio",
        f"   - Subi alquileres.zip (scope=operacional)",
        f"",
        f"3. Post-import (Railway DB UI):",
        f"   - Pega el contenido de post_import.sql",
        f"   - Ejecutar (bumpea las secuencias para no colisionar con futuros pedidos)",
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
    ap.add_argument("--customers", required=True)
    ap.add_argument("--equipos", required=True)
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()

    orders, lines, products, customers, equipos = load_data(args)
    print(f"orders: {len(orders)}, lines: {len(lines)}, products: {len(products)}, "
          f"customers: {len(customers)}, equipos locales: {len(equipos)}", file=sys.stderr)

    idx = build_indices(orders, lines, products, customers, equipos)
    alquileres, placeholders, skipped = build_alquileres(orders, idx)
    stats = write_outputs(Path(args.outdir), alquileres, placeholders, skipped, idx)

    print(f"\nResumen:", file=sys.stderr)
    for k, v in stats.items():
        print(f"  {k:>20}: {v}", file=sys.stderr)
    print(f"\nOutput: {args.outdir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
