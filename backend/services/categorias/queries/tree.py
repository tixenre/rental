"""queries/tree.py — Lecturas del árbol completo para las 2 pantallas que lo
muestran: el catálogo público (`listar_arbol_publico*`) y el admin
(`listar_arbol_admin`). Ambas calculan `total` en vivo (COUNT/JOIN contra
equipo_categorias) — NO usan la columna `categorias.total`, que hoy no la
escribe nadie (queda siempre en 0; ver nota en read.py::listar_categorias_flat)."""
from collections import defaultdict


def _descendants(nid: int, nodes: dict) -> set:
    """BFS de descendientes de nid (incluido) sobre un dict {id: {parent_id,
    ...}} ya cargado en memoria. Auxiliar de listar_arbol_publico — evita un
    round-trip a SQL por nodo para calcular el total del subárbol."""
    out = {nid}
    stack = [nid]
    while stack:
        cur = stack.pop()
        for n in nodes.values():
            if n["parent_id"] == cur:
                out.add(n["id"])
                stack.append(n["id"])
    return out


def listar_arbol_publico(conn) -> list[dict]:
    """Árbol de categorías visibles con conteo de equipos por subárbol.
    Para el GET /categorias público."""
    cats = conn.execute("""
        SELECT id, nombre, prioridad, parent_id, popularidad_score
        FROM categorias
        WHERE COALESCE(visible, TRUE) = TRUE
        ORDER BY prioridad ASC, popularidad_score DESC, LOWER(nombre) ASC
    """).fetchall()

    nodes = {
        r["id"]: {
            "id": r["id"], "nombre": r["nombre"], "prioridad": r["prioridad"],
            "parent_id": r["parent_id"], "total": 0, "children": [],
        }
        for r in cats
    }
    roots = []
    for r in cats:
        n = nodes[r["id"]]
        if r["parent_id"] and r["parent_id"] in nodes:
            nodes[r["parent_id"]]["children"].append(n)
        else:
            roots.append(n)

    eq_rows = conn.execute(
        "SELECT equipo_id, categoria_id FROM equipo_categorias"
    ).fetchall()
    eq_cats: dict[int, set] = defaultdict(set)
    for r in eq_rows:
        eq_cats[r["equipo_id"]].add(r["categoria_id"])

    for nid, n in nodes.items():
        sub = _descendants(nid, nodes)
        n["total"] = sum(1 for tags in eq_cats.values() if tags & sub)

    for n in nodes.values():
        n["children"].sort(key=lambda x: (x["prioridad"], x["nombre"].lower()))
    roots.sort(key=lambda x: (x["prioridad"], x["nombre"].lower()))

    def clean(n):
        return {
            "id": n["id"], "nombre": n["nombre"], "prioridad": n["prioridad"],
            "total": n["total"], "parent_id": n["parent_id"],
            "children": [clean(c) for c in n["children"]],
        }
    return [clean(r) for r in roots]


def listar_arbol_publico_flat(conn) -> list[dict]:
    """Versión plana del árbol público (solo raíces + subtags)."""
    roots = listar_arbol_publico(conn)
    return [
        {
            "nombre": r["nombre"], "total": r["total"], "prioridad": r["prioridad"],
            "subtags": [{"nombre": c["nombre"], "total": c["total"]} for c in r["children"]],
        }
        for r in roots
    ]


def listar_arbol_admin(conn) -> list[dict]:
    """Lista plana de categorías para el admin (con todas las columnas)."""
    rows = conn.execute("""
        SELECT c.id, c.nombre, c.prioridad, c.parent_id,
               COALESCE(c.visible, TRUE) AS visible,
               c.nombre_publico_template,
               COUNT(e.id) AS total
        FROM categorias c
        LEFT JOIN equipo_categorias ec ON ec.categoria_id = c.id
        LEFT JOIN equipos e ON e.id = ec.equipo_id AND e.eliminado_at IS NULL
        GROUP BY c.id, c.nombre, c.prioridad, c.parent_id, c.visible, c.nombre_publico_template
        ORDER BY c.prioridad ASC, LOWER(c.nombre) ASC
    """).fetchall()
    return [
        {"id": r["id"], "nombre": r["nombre"], "prioridad": r["prioridad"],
         "parent_id": r["parent_id"], "visible": bool(r["visible"]),
         "nombre_publico_template": r["nombre_publico_template"],
         "total": r["total"]}
        for r in rows
    ]
