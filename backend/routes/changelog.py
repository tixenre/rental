"""
routes/changelog.py — "Novedades" para el back-office.

Lee los PRs mergeados del repo `tixenre/rental` vía GitHub API y los devuelve
formateados como un feed de cambios. Cachea en memoria 10 minutos para no
quemar el rate limit (60 req/hr sin token, 5000 con `GITHUB_TOKEN`).
"""

from __future__ import annotations

import os
import time
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request

from admin_guard import require_admin

router = APIRouter()

# ── Config ─────────────────────────────────────────────────────────────────
GITHUB_REPO = os.getenv("GITHUB_REPO", "tixenre/rental")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
CACHE_TTL = 600  # 10 min

# ── Caché en memoria ───────────────────────────────────────────────────────
_cache: dict[str, tuple[float, list[dict]]] = {}


def _gh_headers() -> dict[str, str]:
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "rambla-rental-backoffice",
    }
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


def _fetch_prs(limit: int = 30) -> list[dict]:
    """Descarga los últimos PRs cerrados (mergeados o no) ordenados por updated_at."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/pulls"
    params = {
        "state": "closed",
        "sort": "updated",
        "direction": "desc",
        "per_page": str(limit),
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(url, headers=_gh_headers(), params=params)
        if r.status_code == 403 and "rate limit" in r.text.lower():
            raise HTTPException(503, "Rate limit de GitHub agotado. Reintentar en unos minutos.")
        if r.status_code != 200:
            raise HTTPException(502, f"GitHub API → {r.status_code}: {r.text[:200]}")
        return r.json()
    except httpx.HTTPError as e:
        raise HTTPException(502, f"No se pudo contactar a GitHub: {e}")


def _normalize_pr(pr: dict) -> dict:
    """Reduce la respuesta de GitHub a los campos que necesita el frontend."""
    return {
        "number":     pr.get("number"),
        "title":      pr.get("title") or "",
        "body":       (pr.get("body") or "").strip(),
        "html_url":   pr.get("html_url") or "",
        "merged_at":  pr.get("merged_at"),
        "closed_at":  pr.get("closed_at"),
        "user":       (pr.get("user") or {}).get("login", ""),
        "labels":     [(l.get("name") or "") for l in (pr.get("labels") or [])],
        "is_merged":  pr.get("merged_at") is not None,
    }


@router.get("/admin/changelog")
def admin_changelog(request: Request, limit: int = 30, force: bool = False):
    """Devuelve los últimos PRs mergeados del repo, formateados para el feed.

    Query params:
    - `limit` (default 30, max 50): cuántos PRs traer
    - `force=true`: invalida el caché y re-fetcha
    """
    require_admin(request)
    limit = max(1, min(50, int(limit)))

    cache_key = f"prs:{limit}"
    now = time.time()
    if not force and cache_key in _cache:
        ts, data = _cache[cache_key]
        if now - ts < CACHE_TTL:
            return {"items": data, "cached": True, "age_seconds": int(now - ts)}

    raw = _fetch_prs(limit)
    items = [_normalize_pr(p) for p in raw if p.get("merged_at")]
    _cache[cache_key] = (now, items)
    return {"items": items, "cached": False, "age_seconds": 0}
