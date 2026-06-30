"""database/auto_tags.py — etiquetas derivadas origen='auto' (#501 Fase 5).

Regenera las tags automáticas de un equipo (o lote) a partir de su marca/modelo/
nombre/categorías. Move-verbatim desde `database.py`; usa los fragmentos canónicos
de marca del spine (`core`). Lo llama `schema.init_db()` (regenerate_auto_tags_all)
y los routes de equipos al editar.
"""
import re as _re

from database.core import MARCA_SUBQUERY, marca_subquery


_WORD_SPLIT = _re.compile(r"[^\wáéíóúñü]+", flags=_re.UNICODE)


def _auto_tags_from_parts(equipo: dict, categoria_nombres) -> list[str]:
    """Arma la lista de strings que deberían ser etiquetas auto a partir de los
    campos del equipo (marca/modelo/nombre) + los nombres de sus categorías (con
    ancestros, ya resueltos por el caller).

    Es la pieza ÚNICA de la regla de tagging: tanto el camino por-equipo
    (`_auto_tags_for_equipo`) como el batch (`regenerate_auto_tags_batch`) la
    usan, así no pueden divergir qué tags ve un equipo según el camino que lo
    procesó."""
    bag: list[str] = []

    def add(val):
        if not val:
            return
        s = str(val).strip().lower()
        if not s:
            return
        if s not in bag:
            bag.append(s)

    add(equipo.get("marca"))
    add(equipo.get("modelo"))
    # Palabras del nombre (descarta tokens muy cortos / numéricos sueltos).
    for word in _WORD_SPLIT.split(str(equipo.get("nombre") or "")):
        w = word.strip().lower()
        if len(w) >= 3 and not w.isdigit():
            add(w)

    # Nombres de categorías asignadas + sus padres (árbol completo hacia arriba).
    for nombre in categoria_nombres:
        add(nombre)

    return bag


def _auto_tags_for_equipo(conn, equipo: dict) -> list[str]:
    """Calcula la lista de strings que deberían ser etiquetas auto para un equipo."""
    # Nombres de categorías asignadas + sus padres (árbol completo hacia arriba).
    cat_rows = conn.execute("""
        WITH RECURSIVE up AS (
            SELECT c.id, c.nombre, c.parent_id
            FROM equipo_categorias ec
            JOIN categorias c ON c.id = ec.categoria_id
            WHERE ec.equipo_id = %s
            UNION
            SELECT p.id, p.nombre, p.parent_id
            FROM categorias p
            JOIN up ON up.parent_id = p.id
        )
        SELECT DISTINCT nombre FROM up
    """, (equipo["id"],)).fetchall()
    return _auto_tags_from_parts(equipo, [r["nombre"] for r in cat_rows])


def regenerate_auto_tags(conn, equipo_id: int) -> int:
    """
    Regenera las etiquetas `origen='auto'` para un equipo.
    No toca las `origen='manual'`. Devuelve cuántas auto-tags quedaron asignadas.
    """
    eq = conn.execute(
        f"SELECT id, nombre, {marca_subquery('equipos')}, modelo FROM equipos WHERE id = %s", (equipo_id,)
    ).fetchone()
    if not eq:
        return 0
    equipo = {"id": eq["id"], "nombre": eq["nombre"], "marca": eq["marca"], "modelo": eq["modelo"]}

    # 1) Borrar las auto actuales del equipo.
    conn.execute(
        "DELETE FROM equipo_etiquetas WHERE equipo_id = %s AND origen = 'auto'",
        (equipo_id,),
    )

    # 2) Calcular nuevas y asegurar que cada nombre exista en `etiquetas`.
    tags = _auto_tags_for_equipo(conn, equipo)
    count = 0
    for orden, name in enumerate(tags):
        # Upsert de la etiqueta (la tabla tiene UNIQUE(nombre)).
        conn.execute(
            "INSERT INTO etiquetas (nombre) VALUES (%s) ON CONFLICT (nombre) DO NOTHING",
            (name,),
        )
        row = conn.execute("SELECT id FROM etiquetas WHERE nombre = %s", (name,)).fetchone()
        if not row:
            continue
        # Insertar como auto. Si el admin ya tenía esta etiqueta como manual,
        # respetamos su origen (DO NOTHING).
        conn.execute("""
            INSERT INTO equipo_etiquetas (equipo_id, etiqueta_id, orden, origen)
            VALUES (%s, %s, %s, 'auto')
            ON CONFLICT (equipo_id, etiqueta_id) DO NOTHING
        """, (equipo_id, row["id"], orden))
        count += 1

    # Limpiar etiquetas que ya no las usa ningún equipo (ni manual ni auto).
    # `etiquetas` no tiene columna `origen` — el origen vive en `equipo_etiquetas`.
    conn.execute("""
        DELETE FROM etiquetas
        WHERE id NOT IN (SELECT DISTINCT etiqueta_id FROM equipo_etiquetas)
    """)

    return count


# Tamaño de tanda del batch: acota cuántos equipos se cargan a memoria y cuántos
# parámetros viajan en cada query. Las queries usan arrays (`= ANY(...)`), que
# Postgres maneja bien aun con listas grandes; el chunk es defensa de memoria.
_AUTO_TAGS_CHUNK = 1000


def regenerate_auto_tags_batch(conn, equipo_ids) -> int:
    """Variante batch de `regenerate_auto_tags`: regenera las etiquetas
    `origen='auto'` de N equipos en un puñado de queries (en vez de O(N) pasadas
    — una por equipo). El resultado es IDÉNTICO a llamar `regenerate_auto_tags`
    equipo por equipo: mismo set de auto-tags por equipo, se respetan las
    `manual` (ON CONFLICT DO NOTHING) y se limpian las etiquetas huérfanas.

    Usar en los caminos masivos (bulk_action, duplicación, rename de categoría)
    donde antes se iteraba `regenerate_auto_tags` adentro de un loop → N+1.

    Devuelve cuántos equipos se procesaron."""
    ids = list(dict.fromkeys(int(i) for i in equipo_ids))  # dedup preservando orden
    if not ids:
        return 0

    procesados = 0
    for i in range(0, len(ids), _AUTO_TAGS_CHUNK):
        procesados += _regenerate_auto_tags_chunk(conn, ids[i:i + _AUTO_TAGS_CHUNK])

    # Limpiar etiquetas que ya no usa ningún equipo (ni manual ni auto). Igual que
    # en el camino por-equipo, pero UNA sola vez al final en vez de por equipo.
    conn.execute("""
        DELETE FROM etiquetas
        WHERE id NOT IN (SELECT DISTINCT etiqueta_id FROM equipo_etiquetas)
    """)
    return procesados


def _regenerate_auto_tags_chunk(conn, ids) -> int:
    """Procesa una tanda de equipos (sin la limpieza de huérfanas, que hace el
    caller una vez al final). Devuelve cuántos equipos se procesaron."""
    # 1) Cargar marca/modelo/nombre de todos los equipos de la tanda en UNA query.
    #    Alias `e` + helper MARCA_SUBQUERY (convención 2026-05-26).
    eq_rows = conn.execute(
        f"SELECT e.id, e.nombre, {MARCA_SUBQUERY}, e.modelo "
        "FROM equipos e WHERE e.id = ANY(%s)",
        (ids,),
    ).fetchall()
    if not eq_rows:
        return 0
    found_ids = [r["id"] for r in eq_rows]

    # 2) Borrar las auto actuales de todos los equipos de la tanda en UNA query.
    conn.execute(
        "DELETE FROM equipo_etiquetas WHERE equipo_id = ANY(%s) AND origen = 'auto'",
        (found_ids,),
    )

    # 3) Árbol de categorías (con ancestros) de TODOS los equipos en UNA query
    #    recursiva, arrastrando equipo_id para atribuir cada nombre a su equipo.
    cat_rows = conn.execute("""
        WITH RECURSIVE up AS (
            SELECT ec.equipo_id, c.id, c.nombre, c.parent_id
            FROM equipo_categorias ec
            JOIN categorias c ON c.id = ec.categoria_id
            WHERE ec.equipo_id = ANY(%s)
            UNION
            SELECT up.equipo_id, p.id, p.nombre, p.parent_id
            FROM categorias p
            JOIN up ON up.parent_id = p.id
        )
        SELECT DISTINCT equipo_id, nombre FROM up
    """, (found_ids,)).fetchall()
    cats_por_equipo: dict = {}
    for r in cat_rows:
        cats_por_equipo.setdefault(r["equipo_id"], []).append(r["nombre"])

    # 4) Calcular el bag de tags por equipo (misma pieza que el camino por-equipo)
    #    y juntar el universo de nombres de etiquetas de toda la tanda.
    bags: dict = {}
    todos_los_nombres: set = set()
    for r in eq_rows:
        equipo = {"id": r["id"], "nombre": r["nombre"], "marca": r["marca"], "modelo": r["modelo"]}
        bag = _auto_tags_from_parts(equipo, cats_por_equipo.get(r["id"], []))
        bags[r["id"]] = bag
        todos_los_nombres.update(bag)

    # 5) Asegurar que cada nombre exista en `etiquetas` (UNA query) y mapear
    #    nombre → id (UNA query).
    name_to_id: dict = {}
    if todos_los_nombres:
        nombres = list(todos_los_nombres)
        conn.execute(
            "INSERT INTO etiquetas (nombre) SELECT unnest(%s::text[]) "
            "ON CONFLICT (nombre) DO NOTHING",
            (nombres,),
        )
        id_rows = conn.execute(
            "SELECT id, nombre FROM etiquetas WHERE nombre = ANY(%s)",
            (nombres,),
        ).fetchall()
        name_to_id = {row["nombre"]: row["id"] for row in id_rows}

    # 6) Insertar todas las asignaciones auto de la tanda en UNA query (unnest de
    #    arrays paralelos). ON CONFLICT respeta una etiqueta ya marcada manual.
    eq_ids, et_ids, ordenes = [], [], []
    for eid in found_ids:
        for orden, name in enumerate(bags.get(eid, [])):
            etiqueta_id = name_to_id.get(name)
            if etiqueta_id is None:
                continue
            eq_ids.append(eid)
            et_ids.append(etiqueta_id)
            ordenes.append(orden)
    if eq_ids:
        conn.execute("""
            INSERT INTO equipo_etiquetas (equipo_id, etiqueta_id, orden, origen)
            SELECT eq, et, ord, 'auto'
            FROM unnest(%s::int[], %s::int[], %s::int[]) AS t(eq, et, ord)
            ON CONFLICT (equipo_id, etiqueta_id) DO NOTHING
        """, (eq_ids, et_ids, ordenes))

    return len(found_ids)


def regenerate_auto_tags_all(conn) -> int:
    """Regenera auto-tags para todos los equipos. Devuelve cantidad procesada."""
    rows = conn.execute("SELECT id FROM equipos").fetchall()
    return regenerate_auto_tags_batch(conn, [r["id"] for r in rows])
