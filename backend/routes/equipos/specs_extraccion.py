"""routes/equipos/specs_extraccion.py — extracción de specs desde HTML fuente.

Move-verbatim (issue de tracking #1258, Corte B — split estructural puro, sin
optimizar la lógica a pedido del dueño). Cubre los 3 endpoints que procesan
HTML de un equipo para autocompletar specs (`upload-html-source`,
`enriquecer-from-html`, `re-extract-specs`) + su motor compartido
(`_extraer_specs_y_proponer`/`_proponer_no_reconocidos`). Registra sus rutas
en el router compartido del paquete `routes.equipos`.
"""
import logging
from typing import Optional

from fastapi import File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from auth.guards import require_admin
from database import get_db
from routes.equipos.core import router
from services.media.storage import put as _put_r2, get as _get_r2
from services.media_fastapi import media_http

logger = logging.getLogger(__name__)


@router.post("/admin/equipos/{id}/upload-html-source")
async def admin_upload_html_source(
    id: int,
    request: Request,
    file: UploadFile = File(...),
    categoria_hint: Optional[str] = None,
) -> dict:
    """Sube y persiste el HTML guardado de B&H, extrae specs y los devuelve.

    Guarda el blob en R2 (equipos/{id}/source.html), actualiza html_source_url
    en la BD y devuelve AutocompletarResult con los specs extraídos. Una segunda
    llamada sobreescribe el blob anterior (path determinístico sin timestamp).

    Args:
        id: ID del equipo al que se asocia el HTML.
        file: HTML guardado (Cmd+S → Webpage Complete).
        categoria_hint: categoría opcional para saltear auto-detección.

    Returns: {html_source_url, ...AutocompletarResult}
    """
    require_admin(request)

    with get_db() as conn:
        if not conn.execute("SELECT id FROM equipos WHERE id=%s", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")

    content = await file.read()
    if not content:
        raise HTTPException(400, "Archivo vacío")
    if len(content) > 5_000_000:
        raise HTTPException(400, "HTML demasiado grande (máx 5MB)")

    try:
        html_content = content.decode("utf-8", errors="replace")
    except Exception:
        raise HTTPException(400, "HTML inválido (no es UTF-8)")

    path = f"equipos/{id}/source.html"
    with media_http():
        html_source_url = _put_r2(path, content, "text/html; charset=utf-8")

    with get_db() as conn:
        try:
            conn.execute(
                "UPDATE equipos SET html_source_url = %s, updated_at = CURRENT_TIMESTAMP WHERE id=%s",
                (html_source_url, id),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    result = _extraer_specs_y_proponer(id, html_content, categoria_hint)

    return {"html_source_url": html_source_url, **result}


class EnriquecerFromHtmlBody(BaseModel):
    html: str
    categoria_hint: Optional[str] = None


@router.post("/admin/equipos/{id}/enriquecer-from-html")
def admin_enriquecer_from_html(id: int, body: EnriquecerFromHtmlBody, request: Request) -> dict:
    """Hermano JSON de upload-html-source (#1051 Stream B): mismo extractor
    (`extract_from_html`), mismo aprendizaje (#1203) — pero NO persiste nada
    en R2 ni toca `html_source_url`. Para cuando el HTML se consigue pegando
    texto (Chrome MCP, portapapeles) en vez de subir un archivo Cmd+S; el
    admin decide después si además quiere `upload-html-source` para dejarlo
    guardado.

    Returns: AutocompletarResult (mismo shape que upload-html-source, sin
    `html_source_url`).
    """
    require_admin(request)

    with get_db() as conn:
        if not conn.execute("SELECT id FROM equipos WHERE id=%s", (id,)).fetchone():
            raise HTTPException(404, "Equipo no encontrado")

    html_content = (body.html or "").strip()
    if not html_content:
        raise HTTPException(400, "HTML vacío")
    if len(html_content) > 5_000_000:
        raise HTTPException(400, "HTML demasiado grande (máx 5MB)")

    return _extraer_specs_y_proponer(id, html_content, body.categoria_hint)


@router.post("/admin/equipos/{id}/re-extract-specs")
def admin_re_extract_specs(id: int, request: Request, categoria_hint: Optional[str] = None) -> dict:
    """Re-corre la extracción sobre el HTML YA guardado del equipo, sin
    resubir el archivo (#1203) — típicamente después de agregar un spec
    nuevo al registry: los equipos con HTML guardado pueden traer su valor
    de un plumazo en vez de perseguir el archivo original de nuevo.

    Mismo motor (`extract_from_html`) que el upload — resultado idéntico al
    de resubir el mismo archivo. 404 si el equipo no tiene HTML guardado.

    Returns: mismo shape que upload-html-source (AutocompletarResult).
    """
    require_admin(request)

    with get_db() as conn:
        row = conn.execute(
            "SELECT html_source_url FROM equipos WHERE id=%s", (id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Equipo no encontrado")
        html_source_url = dict(row).get("html_source_url")
        if not html_source_url:
            raise HTTPException(404, "Este equipo no tiene HTML fuente guardado")

    path = f"equipos/{id}/source.html"
    with media_http():
        content = _get_r2(path)

    try:
        html_content = content.decode("utf-8", errors="replace")
    except Exception:
        raise HTTPException(400, "HTML guardado inválido (no es UTF-8)")

    result = _extraer_specs_y_proponer(id, html_content, categoria_hint)

    return {"html_source_url": html_source_url, **result}


def _extraer_specs_y_proponer(equipo_id: int, html_content: str, categoria_hint: Optional[str]) -> dict:
    """Corre `extract_from_html` + encola no-reconocidos (#1203). Fuente única
    para los 3 endpoints que procesan HTML de un equipo (upload-html-source,
    re-extract-specs, enriquecer-from-html) — mismo motor, mismo aprendizaje."""
    try:
        from services.specs_ingesta import extract_from_html
        result = extract_from_html(html_content, categoria_hint=categoria_hint)
    except Exception:
        logger.exception("Error extrayendo specs del HTML (equipo %d)", equipo_id)
        raise HTTPException(500, "No se pudo procesar el HTML")

    _proponer_no_reconocidos(equipo_id, result)
    return result


def _proponer_no_reconocidos(equipo_id: int, result: dict) -> None:
    """Encola en la cola de aprendizaje (#1203) los pares sin match de esta
    extracción, atribuidos al equipo. Best-effort: un fallo acá NO debe
    tirar abajo la subida del HTML (ya persistida) ni ocultar las specs
    reconocidas al frontend — solo se pierde la señal de aprendizaje de
    ESTA subida, recuperable resubiendo o con re-extract-specs."""
    unmatched = result.get("unmatched") or []
    if not unmatched:
        return
    try:
        from services.specs_ingesta import proponer_desde_equipo

        with get_db() as conn:
            proponer_desde_equipo(conn, equipo_id, result.get("categoria_sugerida"), unmatched)
            conn.commit()
    except Exception:
        logger.exception("No se pudo encolar specs no reconocidas (equipo %d)", equipo_id)
