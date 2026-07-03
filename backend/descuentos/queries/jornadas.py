"""descuentos/queries/jornadas.py — escala de descuento por cantidad de jornadas.

`obtener_descuento_jornadas` es el move-verbatim de `routes/alquileres/
core.py::_get_descuento_jornadas`, dividido en una función impura (fetchea)
que delega en `interpolar_descuento_jornadas` (PURA, testeable sin DB) —
mismo patrón que `contabilidad/queries/saldos.py`. `listar_descuentos_jornada`
y `obtener_descuento_jornada_por_jornadas` vienen de la route CRUD
(`routes/alquileres/descuentos.py`), que pasa a ser transporte fino sobre
este módulo.
"""
from database import row_to_dict


def interpolar_descuento_jornadas(puntos: list[tuple[int, float]], jornadas: int) -> float:
    """Interpolación lineal entre los puntos ancla de la escala.

    Con puntos [(1, 0%), (2, 3%), (7, 10%)]:
      - 4 jornadas → interpola entre (2,3%) y (7,10%) → 5.8%
      - 7+ jornadas → 10% (se queda en el último punto)

    `puntos` ya ordenados por jornadas ascendente. Lista vacía → 0.0.
    """
    if not puntos:
        return 0.0
    if jornadas <= puntos[0][0]:
        return float(puntos[0][1])
    if jornadas >= puntos[-1][0]:
        return float(puntos[-1][1])
    for i in range(len(puntos) - 1):
        j0, p0 = puntos[i]
        j1, p1 = puntos[i + 1]
        if j0 <= jornadas <= j1:
            t = (jornadas - j0) / (j1 - j0)
            return round(p0 + t * (p1 - p0), 2)
    return 0.0


def obtener_descuento_jornadas(conn, jornadas: int) -> float:
    """% de descuento por jornadas para una cantidad de jornadas dada.

    Fetchea los puntos ancla de `descuentos_jornada` y delega la matemática en
    `interpolar_descuento_jornadas`. `pct` es NUMERIC en la DB (migración
    g1a2b3c4d5e6) → psycopg lo devuelve como Decimal; se coerce a float acá
    para que la interpolación (`t * (p1 - p0)` con t float) no rompa con
    `float * Decimal` → TypeError → cotizar 500 → totales en $0. Pasaba en
    alquileres de jornadas intermedias (las que interpolan entre puntos ancla).
    """
    rows = conn.execute(
        "SELECT jornadas, pct FROM descuentos_jornada ORDER BY jornadas ASC"
    ).fetchall()
    puntos = [(int(r["jornadas"]), float(r["pct"])) for r in rows]
    return interpolar_descuento_jornadas(puntos, jornadas)


def listar_descuentos_jornada(conn) -> list[dict]:
    """Todos los puntos ancla de la escala, ordenados. Público (lo usa el carrito)."""
    rows = conn.execute(
        "SELECT id, jornadas, pct FROM descuentos_jornada ORDER BY jornadas ASC"
    ).fetchall()
    return [row_to_dict(r) for r in rows]


def obtener_descuento_jornada_por_jornadas(conn, jornadas: int) -> dict | None:
    """Un punto ancla puntual por su `jornadas` (clave única). None si no existe."""
    row = conn.execute(
        "SELECT id, jornadas, pct FROM descuentos_jornada WHERE jornadas = %s",
        (jornadas,),
    ).fetchone()
    return row_to_dict(row) if row else None
