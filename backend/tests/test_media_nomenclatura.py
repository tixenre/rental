"""Tests de make_variant_key / make_original_key — nomenclatura canónica de keys R2.

Cubre el esquema legacy (sin entity_id) y el esquema F1+ (con entity_id, slug, gallery,
position). El hash8 en el nombre de variante F1+ garantiza cache-bust al sobreescribir
contenido en el mismo slot de entidad.
"""
import pytest

pytestmark = pytest.mark.unit

from services.media.service import make_variant_key, make_original_key, _slugify


class TestMakeVariantKeyLegacy:
    """Esquema sin entity_id → media/{kind}/{asset_id}/{variant}.{ext}"""

    def test_formato_basico(self):
        key = make_variant_key(kind="equipo", asset_id=42, variant_name="display", ext="webp")
        assert key == "media/equipo/42/display.webp"

    def test_kind_estudio(self):
        key = make_variant_key(kind="estudio", asset_id=7, variant_name="display-sm", ext="webp")
        assert key == "media/estudio/7/display-sm.webp"

    def test_con_entity_id_none_usa_legacy(self):
        key = make_variant_key(kind="marca", asset_id=1, variant_name="display", ext="webp",
                               entity_id=None, entity_slug=None)
        assert key == "media/marca/1/display.webp"


class TestMakeOriginalKeyLegacy:
    """Original sin entity_id → media/{kind}/{asset_id}/original.{ext}"""

    def test_formato_jpeg(self):
        key = make_original_key(kind="equipo", asset_id=42, ext="jpg")
        assert key == "media/equipo/42/original.jpg"

    def test_formato_png(self):
        key = make_original_key(kind="estudio", asset_id=1, ext="png")
        assert key == "media/estudio/1/original.png"


class TestMakeVariantKeyF1Plus:
    """Esquema con entity_id → media/{kind}/{entity_id}-{slug}/{gallery}/{position}/{variant}-{hash8}.{ext}"""

    def test_formato_completo(self):
        key = make_variant_key(
            kind="equipo", asset_id=99, variant_name="display", ext="webp",
            entity_id=42, entity_slug="camara-sony-a7",
            gallery="fotos", position=0,
            content_hash="abc12345def67890",
        )
        assert key == "media/equipo/42-camara-sony-a7/fotos/0/display-abc12345.webp"

    def test_hash8_en_el_nombre(self):
        key = make_variant_key(
            kind="equipo", asset_id=1, variant_name="og", ext="jpg",
            entity_id=7, entity_slug="lente-50mm",
            gallery="fotos", position=2,
            content_hash="ff00112233445566",
        )
        # Solo 8 chars del hash
        assert "ff001122" in key
        assert key.endswith(".jpg")

    def test_cache_bust_imagen_distinta(self):
        """Dos contenidos distintos → hashes distintos → keys distintas → cache-bust."""
        key_a = make_variant_key(
            kind="equipo", asset_id=1, variant_name="display", ext="webp",
            entity_id=42, entity_slug="camara", gallery="fotos", position=0,
            content_hash="aaaa1111" + "0" * 56,
        )
        key_b = make_variant_key(
            kind="equipo", asset_id=2, variant_name="display", ext="webp",
            entity_id=42, entity_slug="camara", gallery="fotos", position=0,
            content_hash="bbbb2222" + "0" * 56,
        )
        assert key_a != key_b  # cache-bust natural

    def test_mismo_contenido_misma_key(self):
        """Misma imagen re-subida → mismo hash → misma key → dedup."""
        hash_ = "abc12345" + "0" * 56
        key_a = make_variant_key(
            kind="equipo", asset_id=1, variant_name="display", ext="webp",
            entity_id=42, entity_slug="camara", gallery="fotos", position=0,
            content_hash=hash_,
        )
        key_b = make_variant_key(
            kind="equipo", asset_id=3, variant_name="display", ext="webp",
            entity_id=42, entity_slug="camara", gallery="fotos", position=0,
            content_hash=hash_,
        )
        assert key_a == key_b  # dedup: mismo contenido → misma key

    def test_sin_content_hash_usa_asset_id(self):
        """Sin hash disponible, cae a asset_id como fallback."""
        key = make_variant_key(
            kind="equipo", asset_id=5, variant_name="display", ext="webp",
            entity_id=10, entity_slug="tripode", gallery="fotos", position=0,
            content_hash=None,
        )
        assert "5" in key  # asset_id como fallback del hash


class TestMakeOriginalKeyF1Plus:
    def test_formato_completo(self):
        key = make_original_key(
            kind="equipo", asset_id=99, ext="jpg",
            entity_id=42, entity_slug="camara-sony-a7",
            gallery="fotos", position=0,
        )
        assert key == "media/equipo/42-camara-sony-a7/fotos/0/original.jpg"

    def test_original_sin_hash(self):
        """El original es privado y no necesita hash para cache-bust."""
        key = make_original_key(
            kind="estudio", asset_id=1, ext="jpg",
            entity_id=3, entity_slug="rambla",
            gallery="portada", position=0,
        )
        assert "original" in key
        # Sin hash8 en el nombre
        parts = key.split("/")
        assert parts[-1] == "original.jpg"


class TestSlugify:
    def test_acentos(self):
        # NFKD strip: á→a, Ñ→N → "Camara Nona" → "camara-nona"
        assert _slugify("Cámara Ñoña") == "camara-nona"

    def test_ya_limpio(self):
        assert _slugify("camara-sony-a7") == "camara-sony-a7"

    def test_trunca(self):
        assert len(_slugify("a" * 100, max_len=10)) <= 10

    def test_vacio_devuelve_x(self):
        assert _slugify("") == "x"
