"""
services/clasificador_heuristico.py — Sugerencia de categoría por patrones.

Recorre el nombre/marca/modelo del equipo y propone una (raíz, subcategoría)
basándose en regex ordenados por especificidad. NO escribe en la DB — solo
sugiere. El admin revisa y aprueba.

Diseñado para los 156 equipos del inventario real (auditados antes). La
heurística cubre ~70-80%; los dudosos pueden refinarse con IA después.

Devuelve para cada equipo:
  {
    "equipo_id": int,
    "raiz_propuesta": str | None,
    "sub_propuesta": str | None,
    "confianza": float (0..1),
    "razon": str   # el patrón que matcheó
  }
"""

import re
from typing import Optional


# Cada patrón: (regex, raíz, subcategoría_o_None, confianza, razón_amigable)
# Orden importa: los más específicos van primero.
# Las regex son case-insensitive y aplican al texto "nombre · marca · modelo".

PATRONES: list[tuple[str, str, Optional[str], float, str]] = [
    # ── Cámaras ─────────────────────────────────────────────────────────
    (r"\bgopro\b|c[aá]mara\s*acci[oó]n", "Cámaras", "Acción", 0.95, "GoPro/cámara acción"),
    (r"insta\s*360|c[aá]mara\s*360", "Cámaras", "Acción", 0.9, "Cámara 360"),
    (r"sony\s*a7\b|sony\s*a9\b|sony\s*zv-?e", "Cámaras", "Foto", 0.85, "Mirrorless foto"),
    (r"\bc[aá]mara\b.*(fx3|fx6|fx9|c70|c200|c300|c500|komodo|raptor|alexa|bmpcc|bmcc)",
     "Cámaras", "Video", 0.95, "Cuerpo de cine"),
    (r"\bc[aá]mara\b", "Cámaras", "Video", 0.8, "Cámara genérica"),

    # ── Adaptadores (categoría raíz; sub-cats por montura on-the-fly) ───
    (r"\badaptador\b.*\b(ef-?e|ef-?rf|ef-?l|m42-?e|speedbooster|metabones)",
     "Adaptadores", None, 0.95, "Adaptador montura"),
    (r"\badaptador\b|\bspeedbooster\b|\bmc-?11\b",
     "Adaptadores", None, 0.85, "Adaptador genérico"),

    # ── Filtros (categoría raíz; sub-cats por diámetro on-the-fly) ──────
    (r"\bfiltro\b.*\b(82|77|72|67|58|52)\s*mm",
     "Filtros", None, 0.9, "Filtro con diámetro"),
    (r"\bfiltro\b|\bpro-?mist\b|\bvariable\s*nd\b",
     "Filtros", None, 0.7, "Filtro genérico"),

    # ── Soportes ────────────────────────────────────────────────────────
    (r"\bgimbal\b|\bsteadicam\b|\bglidecam\b|\bronin\b",
     "Soportes", "Estabilización", 0.95, "Gimbal/estabilizador"),
    (r"\bslider\b|\bdolly\b|\briel\b", "Soportes", "Slider / Dolly / Riel", 0.95, "Slider/dolly"),
    (r"\bc-?stand\b", "Soportes", "C-Stands", 0.95, "C-Stand"),
    (r"\bcar\s*mount\b|soporte.*veh", "Soportes", "Car Mount", 0.9, "Car mount"),
    (r"tr[ií]pod[eé]\b.*\b(foto|elements|xpro|gitzo)",
     "Soportes", "Trípodes foto", 0.85, "Trípode foto"),
    (r"tr[ií]pod[eé]\b.*galera|cabezal.*galera|\bbowl\b",
     "Soportes", "Trípodes video", 0.9, "Trípode video"),
    (r"tr[ií]pod[eé]\b", "Soportes", "Trípodes video", 0.85, "Trípode"),
    # Manfrotto sin "Trípode" explícito: usar el modelo (5xx = video, otros = foto/estudio)
    (r"manfrotto\b.*\b(50[24]|509|504\s*hd|529)\b|head\s*\+?\s*legs",
     "Soportes", "Trípodes video", 0.85, "Manfrotto video"),
    (r"manfrotto\b.*(elements|xpro|mvmxpro|art)",
     "Soportes", "Trípodes foto", 0.85, "Manfrotto foto"),
    (r"manfrotto\s*0\d\b|\bestudio\s*\d+\b",
     "Soportes", "Trípodes video", 0.8, "Stand de estudio"),

    # ── Iluminación ─────────────────────────────────────────────────────
    (r"\bluz\b.*(on-?camera|on\s*camera)|on-?camera.*\bled\b",
     "Iluminación", "On-camera / Flash", 0.9, "Luz on-camera"),
    (r"\bflash\b.*godox\s*v\d|godox\s*v\d", "Iluminación", "On-camera / Flash", 0.9, "Flash"),
    (r"\bluz\b.*\b(led|tubo)\b.*\brgb\b|\brgb\b.*\bled\b|\brgbww?\b",
     "Iluminación", "LED RGB", 0.95, "Luz LED RGB"),
    (r"\bluz\b.*\btubo\b", "Iluminación", "LED RGB", 0.85, "Tubo LED"),
    (r"\bluz\b.*\bled\b", "Iluminación", "LED daylight/bicolor", 0.85, "Luz LED"),
    (r"\bluz\b.*(fresnel|tungsten|arri\s*\d+w|open\s*face|focus\s*light|mole\s*richardson)",
     "Iluminación", "Tungsteno", 0.9, "Tungsteno"),
    (r"\bspotlight\b|spot\s*light", "Iluminación", "LED daylight/bicolor", 0.7, "Spotlight"),
    (r"\bluz\b", "Iluminación", None, 0.7, "Luz genérica"),

    # ── Modificadores ───────────────────────────────────────────────────
    (r"\bsoftbox\b", "Modificadores", "Softbox", 0.95, "Softbox"),
    (r"\bfrenel\s*attach|fresnel\s*attach", "Modificadores", None, 0.7, "Fresnel attachment"),
    (r"\bbandera\b|\bflag\b", "Modificadores", "Banderas", 0.95, "Bandera"),
    (r"\bframe\b.*difusi|difusi[oó]n.*frame|frame\s*\d+x\d+|frame\s*2x|frame\s*4x",
     "Modificadores", "Difusión / Frame", 0.9, "Frame de difusión"),
    (r"\breflector\b|5-en-1|5\s*en\s*1", "Modificadores", "Reflectores", 0.95, "Reflector"),
    (r"globo\s*china|china\s*ball", "Modificadores", "Difusión / Frame", 0.85, "China ball"),
    (r"difusi[oó]n\b.*marco|marco\s*difusi[oó]n|marco\s*negro",
     "Modificadores", "Difusión / Frame", 0.9, "Marco de difusión"),

    # ── Sonido ──────────────────────────────────────────────────────────
    (r"micr[oó]fono\s*shotgun|\bshotgun\b", "Sonido", "Shotgun / Boom", 0.95, "Shotgun"),
    (r"ca[ñn]a\s*boom|\bboom\b.*(mic|carbono|zeppelin)|\bzeppelin\b",
     "Sonido", "Shotgun / Boom", 0.9, "Caña/boom"),
    # DJI SDR / video transmission van a "Monitores y Video", no a Sonido.
    # Sólo mic wireless (DJI Mic, Rode Wireless GO, Lavalier) van acá.
    (r"\blavalier\b|wireless\s*go|dji\s*mic\b|sistema\s*inal[aá]mbrico(?!\s*sdr)",
     "Sonido", "Inalámbricos / Lavalier", 0.9, "Mic inalámbrico"),
    (r"transmisor\s*inal[aá]mbrico\s*(?:sdr|video)|sdr\s*trans|dji\s*sdr",
     "Monitores y Video", "Transmisión inalámbrica", 0.95, "TX/RX video"),
    (r"micr[oó]fono\s*on-?camera|on-?camera.*mic|videomic|mke\s*4",
     "Sonido", "On-camera (sonido)", 0.85, "Mic on-camera"),
    (r"rodecaster|mezclador|grabador\s*est[eé]reo|fp32|zoom\s*h\d",
     "Sonido", "Estudio / Podcast", 0.85, "Audio estudio"),
    (r"micr[oó]fono\s*din[aá]mico|procaster", "Sonido", "Estudio / Podcast", 0.85, "Mic dinámico"),
    (r"\bintercom\b|solidcom|wireless\s*comms", "Sonido", "Intercom", 0.95, "Intercom"),
    (r"micr[oó]fono\b", "Sonido", None, 0.7, "Micrófono genérico"),

    # ── Monitores y Video ───────────────────────────────────────────────
    (r"(transmisor|recepcion?|sdr\s*trans|transmisi[oó]n\s*inal)",
     "Monitores y Video", "Transmisión inalámbrica", 0.9, "TX/RX wireless"),
    (r"\bfollow\s*focus\b|\bmatebox\b|matte\s*box",
     "Monitores y Video", "Follow Focus / Matebox", 0.9, "Follow focus"),
    (r"monitor.*grabador|video\s*assist", "Monitores y Video", "Grabadores", 0.9, "Grabador video"),
    (r"\bmonitor\b", "Monitores y Video", "Monitores", 0.95, "Monitor"),

    # ── Energía ─────────────────────────────────────────────────────────
    (r"bater[ií]a\s*v-?mount|kit\s*bater[ií]as\s*v-?mount|\bv-?mount\b",
     "Energía", "V-Mount", 0.95, "V-Mount"),
    (r"bater[ií]a.*(np-?f|lp-?e6|fz100|np-?se|np\s*serie-?l)",
     "Energía", "NP / LP-E6", 0.95, "Batería NP/LP-E6"),
    (r"\bbater[ií]a\b|cargador|kit\s*bater[ií]as", "Energía", "NP / LP-E6", 0.75, "Batería genérica"),
    (r"distribuci[oó]n\s*el[eé]ctrica|alargue|zapatilla|generador",
     "Energía", "Distribución eléctrica", 0.9, "Distribución"),

    # ── Media y Datos ───────────────────────────────────────────────────
    (r"tarjeta\s*sd|sdxc", "Media y Datos", "Tarjetas SD", 0.95, "Tarjeta SD"),
    (r"tarjeta\s*cfexpress|cfast", "Media y Datos", "Tarjetas CFexpress", 0.95, "CFexpress"),
    (r"\blector\b", "Media y Datos", "Lectores", 0.95, "Lector"),

    # ── Grip ────────────────────────────────────────────────────────────
    # Va al final porque "Avenger" sin tipo claro debe matchear Grip,
    # pero solo si no entró antes (cámaras, soportes, etc).
    (r"\bbrazo\b|boom\s*arm\b(?!.*mic)", "Grip", "Brazos", 0.9, "Brazo de grip"),
    (r"\bclamp\b|cocodrilo|superclamp|c-?clamp",
     "Grip", "Clamps", 0.95, "Clamp"),
    (r"wall\s*plate|baby\s*pin|junior\s*pin",
     "Grip", "Wall plates / pins", 0.9, "Wall plate/pin"),
    (r"\bpinzas?\b|\bcrate\b", "Grip", "Pinzas", 0.9, "Pinza"),
    (r"magic\s*arm|articul.*arm", "Grip", "Brazos", 0.9, "Magic arm"),
    (r"quick\s*release|\bplate\b|\bbase\s*plate", "Grip", "Wall plates / pins", 0.85, "Plate"),
    (r"l[ií]nea\s*de\s*seguridad|safety\s*line",
     "Grip", "Líneas de seguridad", 0.95, "Línea de seguridad"),
    (r"\bsopapa\b|\bsuction\b", "Grip", "Sopapa", 0.95, "Sopapa"),
    (r"\blastre\b|bolsa\s*de\s*arena|sand\s*bag",
     "Grip", "Lastre", 0.95, "Lastre"),
    (r"\bcage\b", "Grip", None, 0.85, "Camera cage"),
    (r"apple\s*box|tres\s*medidas", "Grip", None, 0.85, "Apple box"),
    # Avenger sin tipo: probablemente grip
    (r"^avenger\b", "Grip", None, 0.6, "Avenger genérico"),

    # ── Lentes (al final para no pisar adaptadores que mencionan montura) ──
    # Taxonomía: Zoom / Fijos / Vintage / Especiales. La montura va por filtro spec.
    (r"kit\s*lentes\s*vintage|carl\s*zeiss\s*jena|helios|\bm42\b",
     "Lentes", "Vintage", 0.95, "Lente vintage"),
    (r"\bprobe\b|\blente\b.*\bmacro\b|cinema\s*pl|master\s*prime",
     "Lentes", "Especiales", 0.85, "Lente macro/probe/cinema especial"),
    (r"\blente\b.*\d+-\d+\s*mm", "Lentes", "Zoom", 0.85, "Lente zoom"),
    (r"\blente\b.*\d+\s*mm",     "Lentes", "Fijos", 0.8, "Lente fijo"),
    (r"\blente\b", "Lentes", None, 0.6, "Lente genérico"),

    # ── Estudio y Producción ────────────────────────────────────────────
    (r"backdrop|fondo|seamless", "Estudio y Producción", "Set / Backdrops", 0.85, "Backdrop"),
    (r"rambla\s*estudio|estudio\s*equipos|paquete|kit\s*equipos?|mesa\s*producci",
     "Estudio y Producción", "Paquetes", 0.85, "Paquete/estudio"),

    # ── Casos especiales (efectos, cables, cases) ───────────────────────
    (r"m[aá]quina\s*de\s*humo|smoke|hazer|fog\s*machine",
     "Iluminación", "Práctica / efecto", 0.85, "Máquina de humo/efecto"),
    (r"\bcable\b|sdi\s*cable|hdmi\s*cable|coiled|bnc|elvid|kondor",
     "Monitores y Video", "Transmisión inalámbrica", 0.7, "Cable video"),
    (r"pelican\s*\d|case\s*foam|hard\s*case",
     "Estudio y Producción", "Paquetes", 0.7, "Case/transporte"),
    (r"\bipad\b|tablet\b|^apple$", "Estudio y Producción", "Paquetes", 0.6, "iPad/tablet"),
    # Accesorios de luz: spotlight, fresnel attachment
    (r"fresnel\s*attach|spotlight.*lens\s*kit",
     "Iluminación", "LED daylight/bicolor", 0.7, "Accesorio de luz"),
    # Avenger códigos sueltos (C4462, E390, etc) → Grip genérico ya está en el patrón ^avenger\b
]


def clasificar(nombre: str, marca: Optional[str], modelo: Optional[str]) -> Optional[dict]:
    """Devuelve la propuesta de categoría para un equipo, o None si no
    pudo clasificar con la heurística."""
    text = " ".join(filter(None, [nombre or "", marca or "", modelo or ""]))
    text_lc = text.lower()
    for regex, raiz, sub, confianza, razon in PATRONES:
        if re.search(regex, text_lc, flags=re.IGNORECASE):
            return {
                "raiz": raiz,
                "sub": sub,
                "confianza": confianza,
                "razon": razon,
                "patron": regex,
            }
    return None


def clasificar_lote(equipos: list[dict]) -> list[dict]:
    """Toma una lista de equipos {id, nombre, marca, modelo} y devuelve
    sugerencias para cada uno."""
    out: list[dict] = []
    for eq in equipos:
        prop = clasificar(eq.get("nombre"), eq.get("marca"), eq.get("modelo"))
        out.append({
            "equipo_id": eq["id"],
            "nombre": eq.get("nombre"),
            "marca": eq.get("marca"),
            "modelo": eq.get("modelo"),
            **(prop or {"raiz": None, "sub": None, "confianza": 0.0, "razon": "sin match", "patron": None}),
        })
    return out
