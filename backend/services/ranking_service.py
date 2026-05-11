"""
services/ranking_service.py — Cálculo de popularidad de equipos.

Combina lo manual (`relevancia_manual` que el admin define) con lo
automático (`popularidad_score` calculado desde el historial de pedidos
e ingresos), normalizado por categoría para que un equipo no compita
con todo el inventario sino con sus pares.

El sort final del catálogo:
    ORDER BY relevancia_manual ASC, popularidad_score DESC, nombre ASC

Convención de relevancia_manual (más bajo = más prominente):
    10  → flagship (RED Komodo X, FX9, Alexa Mini)
    30  → premium (FX3, A7S III, Sigma Art)
    60  → workhorse (BMPCC 6K, A7 III)
    100 → default
    200 → secundarios (cables, baterías, plates)
"""

from datetime import datetime
from typing import Optional


# Ventana de tiempo para el cálculo de popularidad (últimos N días).
# 180 días = 6 meses. Captura tendencia reciente sin que un boom de hace
# 2 años distorsione el ranking actual.
VENTANA_DIAS_DEFAULT = 180


def _categorias_raiz_de(conn, equipo_id: int) -> list[int]:
    """Devuelve los IDs de las categorías raíz a las que pertenece el equipo
    (subiendo desde subcategorías si hace falta)."""
    rows = conn.execute(
        """
        SELECT DISTINCT
            CASE WHEN c.parent_id IS NULL THEN c.id ELSE c.parent_id END AS raiz_id
        FROM equipo_categorias ec
        JOIN categorias c ON c.id = ec.categoria_id
        WHERE ec.equipo_id = ?
        """,
        (equipo_id,),
    ).fetchall()
    return [r["raiz_id"] for r in rows]


def calcular_estadisticas_equipo(
    conn,
    equipo_id: int,
    ventana_dias: int = VENTANA_DIAS_DEFAULT,
) -> dict:
    """Calcula cant_pedidos e ingreso_total_ars para un equipo, desde
    `alquiler_items` joined con `alquileres` filtrados por estado y
    ventana temporal.

    Devuelve {cant_pedidos, ingreso_total_ars}.
    """
    estados_validos = ("confirmado", "retirado", "devuelto", "finalizado")
    placeholders = ",".join(["?"] * len(estados_validos))

    # NOTA: alquileres.fecha_desde / fecha_hasta son TEXT (legacy schema).
    # Usamos NULLIF + cast para ser tolerantes a strings vacíos. Filtramos
    # por substring antes del cast para evitar errores en filas malformadas.
    # NOTA: alquileres.fecha_desde / fecha_hasta son TEXT (legacy schema).
    # La resta de date - date en PG devuelve int (días directamente).
    # Filtramos antes del cast con regex para tolerar filas malformadas.
    row = conn.execute(
        f"""
        SELECT
            COUNT(DISTINCT a.id) AS cant_pedidos,
            COALESCE(SUM(
                ai.cantidad * COALESCE(ai.precio_jornada, 0) *
                GREATEST(
                    1,
                    NULLIF(a.fecha_hasta, '')::date - NULLIF(a.fecha_desde, '')::date
                )
            ), 0) AS ingreso_total_ars
        FROM alquiler_items ai
        JOIN alquileres a ON a.id = ai.pedido_id
        WHERE ai.equipo_id = ?
          AND a.estado IN ({placeholders})
          AND a.fecha_desde ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}'
          AND a.fecha_hasta ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}'
          AND NULLIF(a.fecha_desde, '')::date >= CURRENT_DATE - (? || ' days')::interval
        """,
        (equipo_id, *estados_validos, str(ventana_dias)),
    ).fetchone()

    return {
        "cant_pedidos": int(row["cant_pedidos"] or 0),
        "ingreso_total_ars": int(row["ingreso_total_ars"] or 0),
    }


def recalcular_ranking_todos(
    conn,
    *,
    dry_run: bool = False,
    ventana_dias: int = VENTANA_DIAS_DEFAULT,
) -> dict:
    """Recalcula popularidad_score normalizado por categoría para todos los
    equipos. Lo que se calcula:

      1. Para cada equipo: cant_pedidos e ingreso_total_ars (en la ventana).
      2. Para cada categoría raíz: max_pedidos, max_ingreso (de sus equipos).
      3. popularidad_score = round(50 * pedidos/max_p + 50 * ingreso/max_i),
         donde max_p y max_i son los máximos de la categoría a la que pertenece.

    Equipos sin categoría: se rankean contra el universo entero (fallback).

    Devuelve un reporte con cambios y stats.
    """
    rows = conn.execute(
        """
        SELECT id, nombre, popularidad_score, cant_pedidos, ingreso_total_ars
        FROM equipos
        ORDER BY id
        """
    ).fetchall()

    # Paso 1: calcular stats por equipo
    stats_por_equipo: dict[int, dict] = {}
    for r in rows:
        s = calcular_estadisticas_equipo(conn, r["id"], ventana_dias)
        s["categorias_raiz"] = _categorias_raiz_de(conn, r["id"])
        stats_por_equipo[r["id"]] = s

    # Paso 2: maxes por categoría raíz
    max_por_cat: dict[int, dict] = {}      # raiz_id → {max_pedidos, max_ingreso}
    universo = {"max_pedidos": 0, "max_ingreso": 0}
    for s in stats_por_equipo.values():
        universo["max_pedidos"] = max(universo["max_pedidos"], s["cant_pedidos"])
        universo["max_ingreso"] = max(universo["max_ingreso"], s["ingreso_total_ars"])
        for raiz_id in s["categorias_raiz"]:
            slot = max_por_cat.setdefault(raiz_id, {"max_pedidos": 0, "max_ingreso": 0})
            slot["max_pedidos"] = max(slot["max_pedidos"], s["cant_pedidos"])
            slot["max_ingreso"] = max(slot["max_ingreso"], s["ingreso_total_ars"])

    # Paso 3: calcular score y armar reporte
    cambios: list[dict] = []
    sin_cambios = 0

    for r in rows:
        eq_id = r["id"]
        s = stats_por_equipo[eq_id]

        # Tomar el máximo de las categorías a las que pertenece (si tiene
        # varias, usa el max global de esas raíces). Si no tiene categoría,
        # cae al universo.
        if s["categorias_raiz"]:
            max_p = max(max_por_cat[c]["max_pedidos"] for c in s["categorias_raiz"])
            max_i = max(max_por_cat[c]["max_ingreso"] for c in s["categorias_raiz"])
        else:
            max_p = universo["max_pedidos"]
            max_i = universo["max_ingreso"]

        score_pedidos = (s["cant_pedidos"] / max_p * 50) if max_p > 0 else 0
        score_ingreso = (s["ingreso_total_ars"] / max_i * 50) if max_i > 0 else 0
        nuevo_score = round(score_pedidos + score_ingreso)

        cambios_eq = (
            r["popularidad_score"] != nuevo_score
            or r["cant_pedidos"] != s["cant_pedidos"]
            or r["ingreso_total_ars"] != s["ingreso_total_ars"]
        )

        if cambios_eq:
            cambios.append({
                "id": eq_id,
                "nombre": r["nombre"],
                "antes": {
                    "score": r["popularidad_score"],
                    "pedidos": r["cant_pedidos"],
                    "ingreso": r["ingreso_total_ars"],
                },
                "despues": {
                    "score": nuevo_score,
                    "pedidos": s["cant_pedidos"],
                    "ingreso": s["ingreso_total_ars"],
                },
            })
            if not dry_run:
                conn.execute(
                    """
                    UPDATE equipos
                    SET popularidad_score = ?,
                        cant_pedidos = ?,
                        ingreso_total_ars = ?,
                        ranking_actualizado = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        nuevo_score,
                        s["cant_pedidos"],
                        s["ingreso_total_ars"],
                        eq_id,
                    ),
                )
        else:
            sin_cambios += 1

    if not dry_run:
        conn.commit()

    return {
        "total": len(rows),
        "ventana_dias": ventana_dias,
        "cambios": cambios,
        "sin_cambios": sin_cambios,
        "max_por_categoria": {
            c: max_por_cat[c] for c in sorted(max_por_cat.keys())
        },
        "universo": universo,
        "dry_run": dry_run,
    }
