"""routes/dataio.py — Endpoints admin para export/import del catálogo y operacional.

Expone:
    GET /api/admin/dataio/entities
        Lista las entidades disponibles + a qué grupo pertenecen.

    GET /api/admin/dataio/export?entity=<name>|catalog-all|operacional-all|full
        Devuelve JSON individual (una entidad) o ZIP (grupos).
        - catalog-all: ZIP con las 8 entidades del catálogo.
        - operacional-all: ZIP con clientes + alquileres (datos privados).
        - full: ZIP con todo (catálogo + operacional).

    POST /api/admin/dataio/import?scope=operacional
        Sube un ZIP con clientes.json/alquileres.json para upsert. Solo
        operacional desde la UI (catálogo se importa al startup).
        Query param `dry_run=true` para simular.
"""

import io
import json
import logging
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from admin_guard import require_admin
from database import get_db
from dataio import orchestrator
from dataio.paths import CATALOG_ENTITIES, ENTITY_ORDER, OPERATIONAL_ENTITIES

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/admin/dataio/entities")
def list_entities(_admin: dict = Depends(require_admin)):
    """Lista las entidades disponibles agrupadas por scope."""
    return {
        "catalog": list(CATALOG_ENTITIES),
        "operacional": list(OPERATIONAL_ENTITIES),
        "all": list(ENTITY_ORDER),
    }


def _zip_response(zip_bytes: bytes, filename_prefix: str) -> StreamingResponse:
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename_prefix}-{ts}.zip"'
            )
        },
    )


@router.get("/admin/dataio/export")
def export_dataio(
    entity: str = Query("catalog-all", description="entidad o 'catalog-all'|'operacional-all'|'full'"),
    _admin: dict = Depends(require_admin),
):
    """Exporta una entidad como JSON, o un grupo como ZIP."""
    conn = get_db()
    try:
        if entity == "catalog-all":
            zip_bytes = orchestrator.export_to_zip_bytes(conn, list(CATALOG_ENTITIES))
            return _zip_response(zip_bytes, "catalogo")

        if entity == "operacional-all":
            zip_bytes = orchestrator.export_to_zip_bytes(conn, list(OPERATIONAL_ENTITIES))
            return _zip_response(zip_bytes, "operacional")

        if entity == "full":
            zip_bytes = orchestrator.export_to_zip_bytes(conn, list(ENTITY_ORDER))
            return _zip_response(zip_bytes, "backup-full")

        if entity not in ENTITY_ORDER:
            raise HTTPException(
                400,
                f"Entidad inválida: {entity!r}. "
                f"Válidas: {list(ENTITY_ORDER) + ['catalog-all', 'operacional-all', 'full']}",
            )

        try:
            rows = orchestrator.export_entity(conn, entity)
        except Exception as e:
            logger.exception("export_entity falló para %r", entity)
            raise HTTPException(500, f"Export {entity} falló: {type(e).__name__}: {e}")

        ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        return JSONResponse(
            content=rows,
            headers={
                "Content-Disposition": f'attachment; filename="{entity}-{ts}.json"'
            },
        )
    finally:
        conn.close()


@router.post("/admin/dataio/import")
async def import_dataio(
    file: UploadFile = File(...),
    scope: Literal["operacional"] = Query(
        "operacional",
        description="Scope a importar. Solo 'operacional' habilitado desde UI.",
    ),
    dry_run: bool = Query(False, description="Simular sin commitear."),
    _admin: dict = Depends(require_admin),
):
    """Importa un ZIP con JSONs de clientes/alquileres.

    Por seguridad, solo se permite `scope=operacional` desde la UI.
    El catálogo se importa automáticamente al startup desde `/data/catalog/`.
    """
    if scope != "operacional":
        raise HTTPException(400, "Solo scope=operacional permitido desde UI")
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "Solo archivos .zip permitidos")
    content = await file.read()
    if not content:
        raise HTTPException(400, "Archivo vacío")

    conn = get_db()
    try:
        # Hook para imports de migracion (ej. Booqable). Si el ZIP trae
        # un `placeholders_equipos.json`, creamos esos equipos antes
        # de importar alquileres para que las FKs resuelvan. Idempotente.
        placeholders_created = _create_placeholder_equipos(conn, content)

        stats = orchestrator.import_from_zip_bytes(
            conn,
            content,
            only=list(OPERATIONAL_ENTITIES),
            dry_run=dry_run,
        )

        # Bumpear secuencias post-import para que nuevos pedidos manuales
        # no colisionen con los importados. Idempotente.
        sequences_bumped = []
        if not dry_run and stats.get("alquileres", {}).get("inserted", 0) > 0:
            sequences_bumped = _bump_operacional_sequences(conn)

        if not dry_run:
            conn.commit()
        return {
            "ok": True,
            "dry_run": dry_run,
            "stats": stats,
            "total_inserted": sum(s.get("inserted", 0) for s in stats.values()),
            "total_updated": sum(s.get("updated", 0) for s in stats.values()),
            "placeholders_creados": placeholders_created,
            "sequences_bumped": sequences_bumped,
        }
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        raise HTTPException(400, f"Import falló: {e}")
    finally:
        conn.close()


def _create_placeholder_equipos(conn, zip_bytes: bytes) -> int:
    """Si el ZIP trae `placeholders_equipos.json`, inserta esos equipos
    como historicos (cantidad=0, visible_catalogo=0, estado='historico').
    Idempotente: ON CONFLICT (slug) DO NOTHING.

    Pensado para wipe-and-reimport desde sistemas externos (ej. Booqable)
    donde hay items historicos sin equivalente en el catalogo activo.
    """
    import io
    import json
    import zipfile

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for name in zf.namelist():
                if Path(name).name != "placeholders_equipos.json":
                    continue
                placeholders = json.loads(zf.read(name).decode("utf-8"))
                break
            else:
                return 0
    except (zipfile.BadZipFile, json.JSONDecodeError, KeyError):
        return 0

    if not isinstance(placeholders, list):
        return 0

    created = 0
    for p in placeholders:
        slug = (p.get("slug") or "").strip()
        nombre = (p.get("nombre") or "").strip()
        if not slug or not nombre:
            continue
        result = conn.execute(
            """
            INSERT INTO equipos (slug, nombre, cantidad, visible_catalogo, estado)
            VALUES (?, ?, 0, 0, 'historico')
            ON CONFLICT (slug) DO NOTHING
            RETURNING id
            """,
            (slug, nombre),
        ).fetchone()
        if result:
            created += 1
    return created


def _bump_operacional_sequences(conn) -> list[str]:
    """Despues de un import masivo, sube las secuencias al MAX actual.

    Sin esto, nuevos pedidos manuales agarrarian numero_pedido=1 y
    colisionarian con los importados. Idempotente.
    """
    bumped = []
    for seq, table, col in (
        ("alquileres_id_seq", "alquileres", "id"),
        ("alquiler_items_id_seq", "alquiler_items", "id"),
        ("alquiler_pagos_id_seq", "alquiler_pagos", "id"),
        ("clientes_id_seq", "clientes", "id"),
        ("numero_pedido_seq", "alquileres", "numero_pedido"),
    ):
        try:
            conn.execute(
                f"SELECT setval('{seq}', GREATEST(1, "
                f"(SELECT COALESCE(MAX({col}), 0) FROM {table})), true)"
            )
            bumped.append(seq)
        except Exception as e:
            logger.warning("setval %s fallo (no critico): %s", seq, e)
    return bumped


RESET_CONFIRMATION = "BORRAR TODO"

# Secuencias a resetear despues del wipe operacional. Sin reset, los IDs
# de la siguiente import continuarian desde el MAX previo (ej. importar
# desde Booqable arrancaria en id=500 en vez de 1).
_OPERACIONAL_SEQUENCES = (
    "clientes_id_seq",
    "alquileres_id_seq",
    "alquiler_items_id_seq",
    "alquiler_pagos_id_seq",
    "solicitudes_modificacion_id_seq",
    "numero_pedido_seq",
)


@router.post("/admin/dataio/reset-operacional")
def reset_operacional(
    payload: dict = Body(...),
    _admin: dict = Depends(require_admin),
):
    """Borra TODOS los clientes y alquileres (incluidos items/pagos via CASCADE).

    Pensado para hacer un wipe-and-reimport limpio. Requiere que el body
    incluya exactamente {"confirm": "BORRAR TODO"} para evitar disparos
    accidentales. La operacion no es reversible — hacer backup antes.

    Tambien resetea las secuencias de IDs operacionales a 1 para que la
    siguiente import arranque desde cero (clientes, alquileres y sus
    tablas hijas, mas numero_pedido_seq).
    """
    if payload.get("confirm") != RESET_CONFIRMATION:
        raise HTTPException(
            400,
            f"Confirmacion requerida. Enviar {{'confirm': '{RESET_CONFIRMATION}'}}",
        )

    conn = get_db()
    try:
        clientes_before = conn.execute("SELECT COUNT(*) AS n FROM clientes").fetchone()["n"]
        alquileres_before = conn.execute("SELECT COUNT(*) AS n FROM alquileres").fetchone()["n"]

        # alquileres primero: CASCADE limpia items, pagos y solicitudes_modificacion.
        conn.execute("DELETE FROM alquileres")
        conn.execute("DELETE FROM clientes")

        for seq in _OPERACIONAL_SEQUENCES:
            conn.execute(f"ALTER SEQUENCE IF EXISTS {seq} RESTART WITH 1")

        conn.commit()

        return {
            "ok": True,
            "deleted": {
                "clientes": clientes_before,
                "alquileres": alquileres_before,
            },
            "sequences_reset": list(_OPERACIONAL_SEQUENCES),
        }
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        raise HTTPException(500, f"Reset falló: {e}")
    finally:
        conn.close()
