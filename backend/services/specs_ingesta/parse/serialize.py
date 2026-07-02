"""parse/serialize.py — Convierte specs con valor Python crudo (el output de
los mappers de parsers/) a la forma AutocompletarResult
[{spec_key, label, value}], DELEGANDO la representación humana en
services/spec_render (fuente única) en vez de reimplementar el formateo.

Antes: equipo_html_extractor y luces_html_extractor tenían cada uno su
propio mapeo de sufijos de unidad (W/lm/g/fps uno, K/lux el otro,
divergentes) hardcodeado por spec_key, sin usar el `unidad` que el
registry ya declara.

Dos pasos, igual que el resto del sistema:
  1. Canonicalizar: Python crudo → TEXT canónico (mismo formato que
     persistir_specs guarda en equipo_specs.value).
  2. Renderizar: TEXT canónico → texto humano, vía services.spec_render
     (la misma fuente que usa la ficha pública y el nombre auto).

Gotcha #1 (verificado contra los 4 mappers reales, no supuesto): un spec
tipo="rango" llega en 3 formas distintas según qué parser lo produjo —
lista `[24.0, 70.0]` (lentes_parser), dict `{"min": x, "max": y}`
(camaras_parser: iso_nativo/iso_extendido), o string pre-formateado
"2500-7500K" (iluminacion_parser: temperatura_k). Las 3 se normalizan acá.

Gotcha #2 (encontrado corriendo esto contra las 54 páginas reales, no
teórico): NO delegar el tipo "bool" en spec_render.render_spec_value — ahí
`false` renderiza "" (vacío, a propósito: colapsa conectores del nombre
público). Acá el contexto es distinto (preview de extracción / form admin):
un bool en `false` es información real ("Autofocus: No") que tiene que
mostrarse, no desaparecer. Bool se resuelve acá mismo; todo lo demás
(number/rango/multi_enum/enum/string — donde SÍ vivía la duplicación real
de unidades) delega en spec_render."""

from __future__ import annotations


def _canonicalize(spec_def, raw_value):
    """raw_value (str/int/float/bool/list/dict, el output crudo del mapper)
    → TEXT canónico para equipo_specs.value, o None si no se pudo.

    Gotcha #3 (encontrado corriendo esto contra las 54 páginas reales —
    "built_in_light" de la GoPro HERO12 daba 'No' -> 'Sí', un flip real de
    valor, no cosmético): NO todo lo que llega acá está ya tipado por el
    mapper. `_build_result` promueve keys de `extras` (map_*_extras) a
    `specs_para_persistir` cuando matchean el registry — y `extras` son
    strings de display crudos ("No", "Bluetooth"), NO Python bool/list. Si
    a un tipo="bool" le pasás el string "No" directo a serialize_spec_value
    (`"true" if value else "false"`), Python evalúa `bool("No")` → True
    (string no-vacío) → "true". MAL. Regla: un `str` es texto crudo sin
    coercionar (mismo tratamiento que un label de HTML) → coerce_and_serialize
    (bool "No"->false, multi_enum con fuzzy-match); cualquier otro tipo
    Python (bool/int/float/list/dict-normalizado) ya viene bien tipado por
    el mapper → serialize_spec_value."""
    if raw_value is None:
        return None

    from services.specs import coerce_and_serialize
    from services.specs.commands.seed import serialize_spec_value

    tipo = spec_def.tipo
    value = raw_value

    if tipo == "rango" and isinstance(value, dict) and "min" in value and "max" in value:
        value = [value["min"], value["max"]]

    if isinstance(value, str) and tipo != "string":
        return coerce_and_serialize(value, tipo, spec_def.unidad, spec_def.enum_options)

    return serialize_spec_value(spec_def, value)


def specs_dict_to_array(specs_dict: dict, categoria: str) -> list[dict]:
    """{spec_key: valor_crudo} → [{spec_key, label, value}] para el form
    admin / AutocompletarResult. `value` es texto de display (ya
    renderizado), no el canónico crudo.

    Sin template en el registry para una key → fallback defensivo (nunca
    se descarta, se muestra con la key legible como label)."""
    from services.specs import REGISTRY, get_categoria
    from services import spec_render

    cat_reg = get_categoria(categoria) if categoria else None
    if cat_reg is None and categoria:
        cat_reg = REGISTRY.categorias.get(categoria)
    specs_by_key = {s.key: s for s in cat_reg.specs} if cat_reg else {}

    out: list[dict] = []
    for key, raw_value in specs_dict.items():
        if raw_value is None:
            continue
        spec_def = specs_by_key.get(key)
        if spec_def is None:
            out.append({
                "spec_key": key,
                "label": key.replace("_", " ").title(),
                "value": str(raw_value),
            })
            continue

        canonical = _canonicalize(spec_def, raw_value)
        if canonical is None:
            # La coerción falló (ej. un "bool" cuyo raw es texto rico tipo
            # "Mechanical Filter Wheel with 2-Stop..." en vez de Yes/No —
            # pasa con extras promovidas a un spec bool más simple que el
            # dato real). Gotcha #4: NO había que caer en "No" en silencio
            # acá (era un falso negativo) — mostrar el crudo, como el resto
            # de los "sin coercionar".
            display = str(raw_value)
        elif spec_def.tipo == "bool":
            # Explícito acá — spec_render colapsa false a "" (a propósito,
            # para nombres públicos). En esta pantalla false ES información.
            display = "Sí" if canonical == "true" else "No"
        else:
            display = spec_render.render_spec_value(canonical, spec_def.tipo, spec_def.unidad)
        out.append({"spec_key": key, "label": spec_def.label, "value": display})
    return out
