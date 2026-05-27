"""
routes/estudio.py — CRUD del Estudio (singleton) + galería de fotos (E1).
"""

import json
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from admin_guard import require_admin
from database import get_db
from routes.equipos import (
    _download_image_bytes,
    _optimize_image,
    _upload_to_r2,
    _validate_ssrf_only,
)

router = APIRouter()


# ── Helpers internos ─────────────────────────────────────────────────────────

def _foto_path_estudio() -> str:
    ts = int(time.time() * 1000)
    return f"estudio/{ts}.webp"


def _get_estudio_row(conn):
    cur = conn.execute("SELECT * FROM estudio WHERE id = 1")
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Fila estudio no encontrada — ejecutá init_db")
    return row


def _get_fotos(conn) -> list:
    cur = conn.execute(
        "SELECT id, url, path, orden, es_principal, created_at "
        "FROM estudio_fotos WHERE estudio_id = 1 ORDER BY orden, id",
        (),
    )
    rows = cur.fetchall()
    return [
        {
            "id": r["id"],
            "url": r["url"],
            "path": r["path"],
            "orden": r["orden"],
            "es_principal": bool(r["es_principal"]),
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


def _parse_json_field(value) -> list | None:
    if not value:
        return None
    if isinstance(value, list):
        return value
    try:
        return json.loads(value)
    except Exception:
        return None


def _build_response(row, fotos: list) -> dict:
    return {
        "id": row["id"],
        "equipo_id": row["equipo_id"],
        "nombre": row["nombre"],
        "tagline": row["tagline"],
        "descripcion": row["descripcion"],
        "precio_hora": row["precio_hora"],
        "min_horas": row["min_horas"],
        "open_hour": row["open_hour"],
        "close_hour": row["close_hour"],
        "buffer_horas": row["buffer_horas"],
        "pack_activo": bool(row["pack_activo"]),
        "pack_nombre": row["pack_nombre"],
        "pack_descripcion": row["pack_descripcion"],
        "pack_precio": row["pack_precio"],
        "features": _parse_json_field(row["features_json"]),
        "faq": _parse_json_field(row["faq_json"]),
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        "fotos": fotos,
    }


def _insert_foto(conn, url: str, path: str) -> dict:
    cur = conn.execute(
        "SELECT COALESCE(MAX(orden), -1) + 1 AS next_orden FROM estudio_fotos WHERE estudio_id = 1",
        (),
    )
    orden = cur.fetchone()["next_orden"]

    cur2 = conn.execute("SELECT COUNT(*) AS cnt FROM estudio_fotos WHERE estudio_id = 1", ())
    is_first = cur2.fetchone()["cnt"] == 0

    conn.execute(
        "INSERT INTO estudio_fotos (estudio_id, url, path, orden, es_principal) "
        "VALUES (?, ?, ?, ?, ?)",
        (1, url, path, orden, is_first),
    )
    conn.commit()

    cur3 = conn.execute(
        "SELECT id, url, path, orden, es_principal, created_at FROM estudio_fotos "
        "WHERE path = ? AND estudio_id = 1",
        (path,),
    )
    r = cur3.fetchone()
    return {
        "id": r["id"],
        "url": r["url"],
        "path": r["path"],
        "orden": r["orden"],
        "es_principal": bool(r["es_principal"]),
        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
    }


# ── Endpoint público ─────────────────────────────────────────────────────────

@router.get("/estudio")
def get_estudio():
    """Devuelve la configuración pública del estudio + fotos ordenadas."""
    conn = get_db()
    try:
        row = _get_estudio_row(conn)
        fotos = _get_fotos(conn)
        return _build_response(row, fotos)
    finally:
        conn.close()


# ── Endpoints admin ──────────────────────────────────────────────────────────

class EstudioUpdate(BaseModel):
    nombre: Optional[str] = None
    tagline: Optional[str] = None
    descripcion: Optional[str] = None
    precio_hora: Optional[int] = None
    min_horas: Optional[int] = None
    open_hour: Optional[int] = None
    close_hour: Optional[int] = None
    buffer_horas: Optional[int] = None
    pack_activo: Optional[bool] = None
    pack_nombre: Optional[str] = None
    pack_descripcion: Optional[str] = None
    pack_precio: Optional[int] = None
    features_json: Optional[str] = None
    faq_json: Optional[str] = None


@router.patch("/admin/estudio")
def patch_estudio(body: EstudioUpdate, request: Request):
    require_admin(request)

    updates = {k: v for k, v in body.dict().items() if v is not None}
    conn = get_db()
    try:
        if updates:
            set_parts = [f"{k} = ?" for k in updates]
            set_parts.append("updated_at = ?")
            values = list(updates.values())
            values.append(datetime.now(tz=timezone.utc))
            values.append(1)
            conn.execute(
                f"UPDATE estudio SET {', '.join(set_parts)} WHERE id = ?",
                tuple(values),
            )
            conn.commit()
        row = _get_estudio_row(conn)
        fotos = _get_fotos(conn)
        return _build_response(row, fotos)
    finally:
        conn.close()


@router.post("/admin/estudio/upload-foto")
async def upload_foto(request: Request):
    """Sube un archivo (multipart, campo 'file') a R2 y lo registra en estudio_fotos."""
    require_admin(request)

    form = await request.form()
    file = form.get("file")
    if file is None or not hasattr(file, "read"):
        raise HTTPException(400, "Falta el campo 'file' en el form-data")

    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Archivo vacío")
    if len(raw) > 20 * 1024 * 1024:
        raise HTTPException(413, "Archivo muy grande (máx 20 MB)")

    content, ctype, w, h = _optimize_image(raw)
    path = _foto_path_estudio()
    url = _upload_to_r2(path, content, ctype)

    conn = get_db()
    try:
        foto = _insert_foto(conn, url, path)
    finally:
        conn.close()

    return {
        "id": foto["id"],
        "public_url": url,
        "path": path,
        "size": len(content),
        "size_original": len(raw),
        "content_type": ctype,
        "width": w or None,
        "height": h or None,
    }


class UploadFromUrlBody(BaseModel):
    url: str


@router.post("/admin/estudio/upload-foto-from-url")
def upload_foto_from_url(body: UploadFromUrlBody, request: Request):
    """Descarga URL externa, optimiza y sube a R2. SSRF-safe."""
    require_admin(request)

    url = (body.url or "").strip()
    if not url:
        raise HTTPException(400, "URL vacía")

    _validate_ssrf_only(url)

    raw, raw_ctype = _download_image_bytes(url)
    content, ctype, w, h = _optimize_image(raw)
    path = _foto_path_estudio()
    public_url = _upload_to_r2(path, content, ctype)

    conn = get_db()
    try:
        foto = _insert_foto(conn, public_url, path)
    finally:
        conn.close()

    return {
        "id": foto["id"],
        "public_url": public_url,
        "path": path,
        "size": len(content),
        "size_original": len(raw),
        "content_type": ctype,
        "width": w or None,
        "height": h or None,
    }


@router.delete("/admin/estudio/fotos/{foto_id}")
def delete_foto(foto_id: int, request: Request):
    require_admin(request)

    conn = get_db()
    try:
        cur = conn.execute(
            "SELECT id FROM estudio_fotos WHERE id = ? AND estudio_id = 1",
            (foto_id,),
        )
        if not cur.fetchone():
            raise HTTPException(404, "Foto no encontrada")
        conn.execute("DELETE FROM estudio_fotos WHERE id = ?", (foto_id,))
        conn.commit()
    finally:
        conn.close()

    return {"ok": True}


class FotoOrdenItem(BaseModel):
    id: int
    orden: int
    es_principal: bool


class ReorderBody(BaseModel):
    fotos: list[FotoOrdenItem]


@router.patch("/admin/estudio/fotos/orden")
def reorder_fotos(body: ReorderBody, request: Request):
    require_admin(request)

    conn = get_db()
    try:
        for f in body.fotos:
            conn.execute(
                "UPDATE estudio_fotos SET orden = ?, es_principal = ? "
                "WHERE id = ? AND estudio_id = 1",
                (f.orden, f.es_principal, f.id),
            )
        conn.commit()
        fotos = _get_fotos(conn)
    finally:
        conn.close()

    return {"fotos": fotos}
