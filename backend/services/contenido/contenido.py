"""Puerta única de "qué incluye un producto" (display) — derivada de la receta real.

PROBLEMA QUE RESUELVE: hoy la lista de componentes de un kit/combo para MOSTRAR se
arma en varios lugares con queries separadas (catálogo, ficha, documentos, detalle
de pedido). Coinciden, pero son varias oportunidades de drift. Esta es la **puerta
única**: todos derivan de acá, de la MISMA tabla `kit_componentes` que el motor de
reservas usa para reservar → lo mostrado no puede desincronizarse de lo reservado.

GRANULARIDAD: devuelve los componentes **DIRECTOS (1 nivel)** — "este kit trae estas
cosas" — que es lo que se muestra. El gate, en cambio, expande RECURSIVAMENTE hasta
las hojas para el stock (`reservas.semantics.expandir_demanda`): otra granularidad,
otro propósito. La garantía no es "lista idéntica", es **misma fuente**: el conjunto
de aristas directas de la puerta == el de `reservas.semantics.componentes_de`
(restringido a equipos no eliminados) — lo clava `test_contenido_puerta_db.py`.

NO toca el motor de reservas (sagrado): solo emite SELECTs de lectura, no toma locks
ni transacciones. Filtra `eliminado_at IS NULL` (criterio canónico de display:
un componente soft-deleted no se muestra) — unifica el drift que había entre
`attach_kit` (filtraba) y `get_kit` (no).
"""
from database import MARCA_SUBQUERY, row_to_dict


def _build_query(ph: str, solo_activos: bool) -> str:
    # Componentes DIRECTOS (1 nivel) decorados con los campos de equipo que algún
    # consumidor necesita (superset). Alias `e` para reusar MARCA_SUBQUERY
    # (MEMORIA 2026-05-26).
    #
    # `solo_activos` controla el filtro de soft-delete — y NO es universal:
    #   · True  (catálogo/ficha): un componente soft-deleted NO se muestra (no
    #     ofrecer fierro retirado). Es el default.
    #   · False (documentos/detalle de pedido): se muestran TODOS los componentes
    #     que la receta referencia, incluso retirados — un remito/pedido existente
    #     debe reflejar lo que realmente lleva, aunque una pieza se haya dado de
    #     baja después. Cada consumidor preserva su criterio actual (move-verbatim).
    filtro_activo = "AND e.eliminado_at IS NULL" if solo_activos else ""
    return f"""
        SELECT kc.equipo_id,
               kc.id            AS kc_id,
               kc.componente_id,
               kc.cantidad,
               kc.orden,
               kc.descuento_pct,
               kc.esencial,
               e.nombre,
               {MARCA_SUBQUERY},
               e.modelo,
               e.serie,
               e.valor_reposicion,
               e.foto_url,
               e.foto_url_sm,
               e.foto_url_thumb,
               e.nombre_publico,
               e.nombre_publico_largo,
               e.visible_catalogo,
               e.cantidad       AS stock_total
        FROM kit_componentes kc
        JOIN equipos e ON e.id = kc.componente_id {filtro_activo}
        WHERE kc.equipo_id IN ({ph})
        ORDER BY kc.equipo_id, kc.orden ASC, e.nombre ASC
    """


def query_contenido_batch(equipo_ids, solo_activos: bool = True) -> tuple[str, tuple] | None:
    """SQL + params del batch de contenido — separado de la ejecución para que
    un caller que ya corre OTRAS queries independientes (ej. el pipeline de
    `services.catalogo.proyeccion.proyectar_lista`, #1240) pueda incluir esta
    en el mismo lote sin re-implementar el SQL (rompería la puerta única).
    `None` si `equipo_ids` está vacío — no hay query válida que armar.

    Uso normal (un caller aislado): seguir usando `contenido_de_batch`/
    `contenido_de` de más abajo. Esta función es SOLO para componer con
    `shape_contenido_rows` cuando el caller maneja su propio pipeline/batch de
    queries — no bypasea la puerta única, solo separa "armar el SQL" de
    "ejecutarlo"."""
    ids = list(dict.fromkeys(int(e) for e in equipo_ids))
    if not ids:
        return None
    ph = ",".join("%s" for _ in ids)
    return _build_query(ph, solo_activos), tuple(ids)


def shape_contenido_rows(rows, equipo_ids) -> dict[int, list[dict]]:
    """Da forma `{equipo_id: [componente_dict, ...]}` a filas YA obtenidas de
    `query_contenido_batch` (ver ahí el motivo de separar armado de ejecución).
    Equipos sin componentes (o todos filtrados) aparecen con lista vacía."""
    ids = list(dict.fromkeys(int(e) for e in equipo_ids))
    out: dict[int, list[dict]] = {eid: [] for eid in ids}
    for r in rows:
        d = row_to_dict(r)
        out.setdefault(d["equipo_id"], []).append(d)
    return out


def contenido_de_batch(conn, equipo_ids, solo_activos: bool = True) -> dict[int, list[dict]]:
    """Componentes directos (display) de VARIOS equipos en una query.

    Devuelve `{equipo_id: [componente_dict, ...]}` con la forma de
    `ComponenteContenido`. Equipos sin componentes (simples, o todos filtrados)
    aparecen con lista vacía. Cada `componente_dict` se proyecta al shape que cada
    consumidor ya devuelve (es un superset). Solo lectura — no toma locks.

    `solo_activos=True` (default, catálogo/ficha) filtra los componentes
    soft-deleted; `False` (documentos/detalle de pedido) los incluye. Ver
    `_build_query` para el porqué de que NO sea universal.
    """
    query = query_contenido_batch(equipo_ids, solo_activos)
    if query is None:
        return {}
    sql, params = query
    rows = conn.execute(sql, params).fetchall()
    return shape_contenido_rows(rows, equipo_ids)


def contenido_de(conn, equipo_id: int, solo_activos: bool = True) -> list[dict]:
    """Componentes directos (display) de UN equipo (escalar; delega en el batch)."""
    return contenido_de_batch(conn, [equipo_id], solo_activos).get(int(equipo_id), [])
