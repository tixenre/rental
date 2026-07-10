"""Tests de F4: marcas.logo_url_sm — srcset para BrandCarousel.

- schema: columna logo_url_sm en init_db() (verificado mediante DDL)
- upload raster: deriva display + display-sm → guarda logo_url_sm
- API pública /api/marcas: devuelve logo_url_sm en el SELECT
"""
from unittest.mock import patch, MagicMock, AsyncMock

from starlette.requests import Request


# ── Schema ────────────────────────────────────────────────────────────────────

def test_schema_marcas_tiene_logo_url_sm():
    """_init_db_schema() incluye la columna logo_url_sm en su DDL para marcas."""
    import database.schema as schema_mod
    import inspect
    src = inspect.getsource(schema_mod._init_db_schema)
    assert "logo_url_sm" in src, "_init_db_schema() no define la columna logo_url_sm en marcas"


# ── API pública: SELECT incluye logo_url_sm ───────────────────────────────────

def test_list_marcas_select_incluye_logo_url_sm():
    """list_marcas() incluye logo_url_sm en el SELECT enviado a la BD."""
    import inspect
    import routes.marcas as m
    src = inspect.getsource(m.list_marcas)
    assert "logo_url_sm" in src, "list_marcas() no incluye logo_url_sm en el SELECT"


# ── Upload raster: derive_specs incluye display-sm ────────────────────────────

def test_upload_raster_specs_incluyen_display_sm():
    """admin_upload_marca_logo pasa [display, display-sm] a store_upload (raster)."""
    import routes.marcas as m
    import inspect
    src = inspect.getsource(m.admin_upload_marca_logo)
    assert "DISPLAY_KEEP_ASPECT_SM" in src, "admin_upload_marca_logo no usa DISPLAY_KEEP_ASPECT_SM"


def test_upload_raster_guarda_logo_url_sm():
    """El UPDATE de upload incluye logo_url_sm."""
    import routes.marcas as m
    import inspect
    src = inspect.getsource(m.admin_upload_marca_logo)
    assert "logo_url_sm" in src, "admin_upload_marca_logo no incluye logo_url_sm en el UPDATE"


# ── Integración: upload real con mocks ───────────────────────────────────────

def test_upload_raster_integra_display_sm():
    """admin_upload_marca_logo llama store_upload con ambos specs y guarda logo_url_sm."""
    fake_asset = MagicMock()
    fake_display = MagicMock(url="https://cdn/display.webp", key="k", bytes=1000,
                             content_type="image/webp", width=1200, height=800)
    fake_sm = MagicMock(url="https://cdn/display-sm.webp")
    fake_asset.variant.side_effect = lambda name: fake_display if name == "display" else fake_sm

    captured = {}

    def fake_store_upload(raw, *, kind, derive_specs, conn, **kw):
        captured["derive_specs"] = derive_specs
        return fake_asset

    with (
        patch("routes.marcas.get_db") as mock_db,
        patch("routes.marcas.require_admin"),
        patch("services.media.store_upload", fake_store_upload),
        patch("services.media_fastapi.media_http"),
    ):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = {"id": 1, "nombre": "Canon"}
        conn.__enter__ = lambda s: conn
        conn.__exit__ = MagicMock(return_value=False)
        mock_db.return_value = conn

        import asyncio

        async def fake_form():
            file_mock = AsyncMock()
            file_mock.read.return_value = b"PNG" * 400  # > 0 bytes, no SVG
            file_mock.filename = "logo.png"
            file_mock.content_type = "image/png"
            return {"file": file_mock}

        import routes.marcas as m
        # Request real (no un MagicMock) — admin_upload_marca_logo lleva
        # `@limiter.limit` (barrido de seguimiento #1263/#1265): slowapi exige
        # una instancia genuina de `starlette.requests.Request`. `.form` se
        # sobreescribe igual que antes (Request no usa __slots__).
        req = Request(
            {"type": "http", "method": "POST", "path": "/admin/marcas/1/upload-logo",
             "headers": [], "client": ("127.0.0.1", 0)}
        )
        req.form = fake_form

        asyncio.run(m.admin_upload_marca_logo(1, req))

    specs = captured.get("derive_specs", [])
    names = [s.name for s in specs]
    assert "display" in names, f"Falta spec 'display'; got {names}"
    assert "display-sm" in names, f"Falta spec 'display-sm'; got {names}"

    # El UPDATE debe incluir logo_url_sm
    update_calls = [str(c) for c in conn.execute.call_args_list]
    assert any("logo_url_sm" in c for c in update_calls), (
        f"logo_url_sm no encontrado en UPDATE. Calls: {update_calls}"
    )
