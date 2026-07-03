"""queries/validation.py — Invariantes del árbol de categorías: nombre único,
profundidad máxima (3 niveles) y ausencia de ciclos. `profundidad_de` /
`max_profundidad_descendiente` son helpers internos de `validar_profundidad`
(no se re-exportan en el `__init__.py` del paquete — nadie afuera los llama
directo)."""
from collections import deque

from ..errors import ErrorValidacion, CategoriaNoExiste, NombreDuplicado


def profundidad_de(conn, node_id: int) -> int:
    """Profundidad de node_id contando desde la raíz (raíz = 0). Cap en 10
    como red de seguridad si una cadena de parent_id quedara corrupta/cíclica
    por fuera de este módulo (no debería pasar — detectar_ciclo lo previene)."""
    d = 0
    cur = node_id
    while True:
        r = conn.execute(
            "SELECT parent_id FROM categorias WHERE id = %s", (cur,)
        ).fetchone()
        if not r or r["parent_id"] is None:
            return d
        d += 1
        cur = r["parent_id"]
        if d > 10:
            return d


def max_profundidad_descendiente(conn, node_id: int) -> int:
    """Cuántos niveles baja el sub-árbol de node_id (0 = sin hijos)."""
    q = deque([(node_id, 0)])
    m = 0
    while q:
        nid, d = q.popleft()
        m = max(m, d)
        children = conn.execute(
            "SELECT id FROM categorias WHERE parent_id = %s", (nid,)
        ).fetchall()
        for ch in children:
            q.append((ch["id"], d + 1))
    return m


def validar_profundidad(conn, parent_id: int, node_id: int | None = None) -> None:
    """Levanta ErrorValidacion si colgar `node_id` (o un nodo nuevo, si
    node_id es None) de `parent_id` excede 3 niveles totales — cuenta la
    profundidad del padre + el propio sub-árbol de node_id (si ya tiene
    hijos, moverlo empuja a esos hijos también)."""
    new_parent_depth = profundidad_de(conn, parent_id)
    own_max_depth = max_profundidad_descendiente(conn, node_id) if node_id is not None else 0
    if new_parent_depth + 1 + own_max_depth > 2:
        raise ErrorValidacion("Excede el máximo de 3 niveles de categorías")


def detectar_ciclo(conn, node_id: int, candidate_parent_id: int) -> None:
    """Levanta ErrorValidacion si candidate_parent_id es descendiente de
    node_id — evita crear un ciclo al reasignar parent_id. El caso
    "node_id no puede ser su propio padre" se valida aparte, en el caller
    (crud.py::actualizar), antes de llegar acá."""
    descendants = set()
    q = deque([node_id])
    while q:
        nid = q.popleft()
        children = conn.execute(
            "SELECT id FROM categorias WHERE parent_id = %s", (nid,)
        ).fetchall()
        for ch in children:
            descendants.add(ch["id"])
            q.append(ch["id"])
    if candidate_parent_id in descendants:
        raise ErrorValidacion("No se puede mover bajo un descendiente (ciclo)")


def validar_nombre_unico(conn, nombre: str, exclude_id: int | None = None) -> None:
    """Levanta NombreDuplicado si ya existe otra categoría con este nombre
    (case-insensitive). `exclude_id` excluye la propia fila en un rename."""
    query = "SELECT id, nombre FROM categorias WHERE LOWER(nombre) = LOWER(%s)"
    params = [nombre]
    if exclude_id is not None:
        query += " AND id != %s"
        params.append(exclude_id)
    choca = conn.execute(query, params).fetchone()
    if choca:
        raise NombreDuplicado(f"Ya existe una categoría llamada '{choca['nombre']}'")


def validar_existe(conn, cid: int) -> None:
    """Levanta CategoriaNoExiste si cid no es una categoría real."""
    if not conn.execute(
        "SELECT id FROM categorias WHERE id = %s", (cid,)
    ).fetchone():
        raise CategoriaNoExiste(f"Categoría {cid} no existe")
