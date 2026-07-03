"""commands/proponer.py — El embudo que aprende: unmatched frecuente → propuesta.

Único lado-ESCRITURA de `specs_ingesta` (CQRS-lite: `queries/` nunca muta,
esto sí). Consume el `unmatched` que `queries/resolver.py::resolve_pairs` ya
descarta como "sin alias conocido" — cuando el MISMO label (normalizado)
aparece con frecuencia suficiente a través de varios HTMLs de la misma
categoría, es señal de un spec real que falta en el registry, no ruido de
una sola página. Se propone vía Canal C (`services.specs.encolar_propuesta`)
— **nunca** escribe el registry directo (código = fuente única de aliases,
ver `services/specs/CLAUDE.md`); un humano revisa y, si corresponde, edita el
registry a mano y re-siembra."""

from __future__ import annotations

from services.specs import encolar_propuesta, listar_propuestas_pendientes
from services.specs_ingesta.queries.resolver import normalize_label

_ORIGEN_LIVE = "specs_ingesta.live"


def proponer_desde_unmatched(
    conn,
    categoria: str,
    unmatched_por_html: list[list[dict]],
    *,
    umbral_minimo: int = 3,
    origen: str = "specs_ingesta.proponer",
) -> list[int]:
    """`unmatched_por_html`: una lista por HTML procesado, cada una la lista
    `unmatched` (`[{"label": ..., "value": ...}, ...]`) que devolvió
    `resolve_pairs` para ESE HTML — todos de la misma `categoria`. El
    llamador (`cli.py`, batch) es quien acumula esto corriendo la extracción
    sobre varios HTMLs; esta función solo agrupa y decide qué proponer.

    Un mismo label que aparece 2 veces en el MISMO HTML cuenta 1 (evita que
    una tabla repetida infle el conteo); tiene que aparecer en >= `umbral_minimo`
    HTMLs *distintos* para proponerse. Deduplicado contra lo que ya está
    pendiente en la cola (mismo label normalizado + categoría) — correr esto
    dos veces sobre el mismo dataset no duplica la propuesta.

    Devuelve los ids de las propuestas nuevas encoladas (puede ser lista vacía
    si nada cruza el umbral o todo ya estaba pendiente)."""
    ya_pendientes = {
        p["payload"].get("label_normalizado")
        for p in listar_propuestas_pendientes(conn)
        if p["tipo"] == "spec_nueva" and p["payload"].get("categoria") == categoria
    }

    conteos: dict[str, dict] = {}
    for unmatched in unmatched_por_html:
        vistos_este_html: set[str] = set()
        for pair in unmatched:
            key = normalize_label(pair["label"])
            if key in vistos_este_html:
                continue
            vistos_este_html.add(key)
            entry = conteos.setdefault(key, {"label": pair["label"], "count": 0, "ejemplos": []})
            entry["count"] += 1
            if len(entry["ejemplos"]) < 5:
                entry["ejemplos"].append(pair["value"])

    ids: list[int] = []
    for key, entry in conteos.items():
        if entry["count"] < umbral_minimo or key in ya_pendientes:
            continue
        propuesta_id = encolar_propuesta(
            conn,
            tipo="spec_nueva",
            payload={
                "categoria": categoria,
                "label": entry["label"],
                "label_normalizado": key,
                "count": entry["count"],
                "ejemplos": entry["ejemplos"],
            },
            origen=origen,
            confianza=min(1.0, entry["count"] / 10),
        )
        ids.append(propuesta_id)
    return ids


def proponer_desde_equipo(
    conn,
    equipo_id: int,
    categoria: str | None,
    unmatched: list[dict],
    *,
    origen: str = _ORIGEN_LIVE,
) -> list[int]:
    """Segundo productor de Canal C (#1203): el upload en vivo de UN equipo,
    SIN umbral — a diferencia de `proponer_desde_unmatched` (agregado, ≥3
    HTMLs de un batch offline), acá cada par sin match de ESTE equipo se
    encola directo, atribuido a `equipo_id`. Con pocos equipos el umbral de
    3 casi nunca dispara; el panel admin agrupa por label al mostrar (ver
    `services.specs.listar_no_reconocidos_agrupados`), así que no hace falta
    esperar repetición para no perder señal.

    Dedup: si ESTE equipo ya tiene una propuesta pendiente para el mismo
    label normalizado, no duplica (re-subir el mismo HTML dos veces no
    infla la cola). Sin `categoria` (detección falló) no propone nada —
    no hay dónde clasificar la propuesta.

    Devuelve los ids de las propuestas nuevas encoladas."""
    if not categoria or not unmatched:
        return []

    ya_pendientes = {
        p["payload"].get("label_normalizado")
        for p in listar_propuestas_pendientes(conn)
        if p["tipo"] == "spec_nueva" and p.get("equipo_id") == equipo_id
    }

    vistos: set[str] = set()
    ids: list[int] = []
    for pair in unmatched:
        key = normalize_label(pair["label"])
        if key in vistos or key in ya_pendientes:
            continue
        vistos.add(key)
        propuesta_id = encolar_propuesta(
            conn,
            tipo="spec_nueva",
            payload={
                "categoria": categoria,
                "label": pair["label"],
                "label_normalizado": key,
                "count": 1,
                "ejemplos": [pair["value"]],
            },
            origen=origen,
            confianza=None,
            equipo_id=equipo_id,
        )
        ids.append(propuesta_id)
    return ids
