"""Tests del slugify de dataio."""

import pytest

from dataio.slug import equipo_slug, slug_unico, slugify


pytestmark = pytest.mark.unit


class TestSlugify:
    def test_basico(self):
        assert slugify("Sony FX3") == "sony-fx3"

    def test_quita_acentos(self):
        assert slugify("Cámara fotográfica") == "camara-fotografica"

    def test_colapsa_guiones(self):
        assert slugify("Sony  FX3  ---  Cinema") == "sony-fx3-cinema"

    def test_idempotente(self):
        s = slugify("Sony FX3 Cinema Camera")
        assert slugify(s) == s

    def test_trim(self):
        assert slugify("  Sony  ") == "sony"
        assert slugify("---Sony---") == "sony"

    def test_caracteres_especiales(self):
        assert slugify("Aputure 600D Pro (Mark II)") == "aputure-600d-pro-mark-ii"

    def test_max_len(self):
        long = "a" * 100
        assert len(slugify(long)) <= 80

    def test_vacio(self):
        assert slugify("") == ""
        assert slugify("   ") == ""


class TestEquipoSlug:
    def test_marca_y_modelo(self):
        assert equipo_slug("Sony", "FX3") == "sony-fx3"

    def test_solo_marca(self):
        assert equipo_slug("Sony", None) == "sony"

    def test_solo_modelo(self):
        assert equipo_slug(None, "FX3") == "fx3"

    def test_ninguno_cae_a_nombre(self):
        assert equipo_slug(None, None, "Sony FX3 Cinema") == "sony-fx3-cinema"

    def test_marca_vacia_cae_a_nombre(self):
        assert equipo_slug("", "", "Sony FX3") == "sony-fx3"

    def test_todo_vacio(self):
        assert equipo_slug(None, None, None) == ""
        assert equipo_slug("", "", "") == ""


class TestSlugUnico:
    """Regla canónica de desambiguación (fuente única: backfill + alta + CLI)."""

    def test_libre_pasa_directo(self):
        assert slug_unico("sony-fx3", set()) == "sony-fx3"

    def test_colision_sufijo_desde_2(self):
        assert slug_unico("sony-fx3", {"sony-fx3"}) == "sony-fx3-2"

    def test_colisiones_consecutivas(self):
        ocupados = {"sony-fx3", "sony-fx3-2", "sony-fx3-3"}
        assert slug_unico("sony-fx3", ocupados) == "sony-fx3-4"

    def test_no_muta_el_set(self):
        ocupados = {"sony-fx3"}
        slug_unico("sony-fx3", ocupados)
        assert ocupados == {"sony-fx3"}  # el caller reserva, no la función
