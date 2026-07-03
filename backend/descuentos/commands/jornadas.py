"""descuentos/commands/jornadas.py — única puerta de escritura de la escala.

Move-verbatim de la lógica de `POST/DELETE /admin/descuentos-jornada`
(`routes/alquileres/descuentos.py`), que pasa a ser transporte HTTP fino
sobre estas funciones. `eliminar_descuento_jornada` hace DELETE real (no
soft-delete) a propósito: `descuentos_jornada` es una tabla de configuración/
escala, no una entidad de plata con `created_by`/`anulado_*` como las de
`contabilidad/` — agregarle esa infraestructura acá sería scope creep de
schema fuera de un split move-verbatim.
"""
from descuentos.queries.jornadas import obtener_descuento_jornada_por_jornadas


def validar_descuento_jornada(data: dict) -> None:
    """Valida forma de un punto ancla nuevo/editado. Levanta ValueError (el
    route lo atrapa y responde 400)."""
    if data.get("jornadas", 0) < 1:
        raise ValueError("jornadas debe ser >= 1")
    pct = data.get("pct")
    if pct is None or not (0 <= pct <= 100):
        raise ValueError("pct debe estar entre 0 y 100")


def crear_descuento_jornada(conn, *, jornadas: int, pct: float) -> dict:
    """Crea o actualiza (upsert por `jornadas`, clave única) un punto ancla
    de la escala. Devuelve la fila resultante."""
    validar_descuento_jornada({"jornadas": jornadas, "pct": pct})
    conn.execute(
        "INSERT INTO descuentos_jornada (jornadas, pct) VALUES (%s, %s) "
        "ON CONFLICT (jornadas) DO UPDATE SET pct = EXCLUDED.pct",
        (jornadas, pct),
    )
    conn.commit()
    return obtener_descuento_jornada_por_jornadas(conn, jornadas)


def eliminar_descuento_jornada(conn, id: int) -> None:
    """Borra un punto ancla. DELETE real — ver nota del módulo."""
    conn.execute("DELETE FROM descuentos_jornada WHERE id = %s", (id,))
    conn.commit()
