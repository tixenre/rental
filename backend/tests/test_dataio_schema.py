"""Tests del schema Pydantic de dataio (validación de JSONs)."""

import pytest
from pydantic import ValidationError

from dataio import schema


pytestmark = pytest.mark.unit


class TestMarca:
    def test_minimo(self):
        m = schema.Marca(nombre="Sony")
        assert m.nombre == "Sony"
        assert m.visible is True
        assert m.orden == 100
        assert m.logo_url is None

    def test_completo(self):
        m = schema.Marca(
            nombre="Sony", logo_url="https://x/sony.png",
            visible=False, orden=5, destacada=True,
        )
        assert m.orden == 5
        assert m.destacada is True

    def test_rechaza_campos_extra(self):
        with pytest.raises(ValidationError):
            schema.Marca(nombre="Sony", campo_inventado=True)


class TestCategoria:
    def test_raiz(self):
        c = schema.Categoria(nombre="Cámaras")
        assert c.parent_path is None

    def test_hija(self):
        c = schema.Categoria(nombre="Foto", parent_path="Cámaras")
        assert c.parent_path == "Cámaras"


class TestSpecDefinition:
    def test_global_sin_categoria(self):
        sd = schema.SpecDefinition(
            spec_key="peso_g", label="Peso", tipo="number",
        )
        assert sd.categoria_raiz_nombre is None

    def test_enum(self):
        sd = schema.SpecDefinition(
            categoria_raiz_nombre="Cámaras",
            spec_key="sensor",
            label="Sensor",
            tipo="enum",
            enum_options=["Full Frame", "APS-C", "MFT"],
        )
        assert sd.enum_options == ["Full Frame", "APS-C", "MFT"]

    def test_tipo_invalido(self):
        with pytest.raises(ValidationError):
            schema.SpecDefinition(
                spec_key="foo", label="Foo", tipo="invento",
            )


class TestEquipo:
    def test_minimo(self):
        e = schema.Equipo(slug="sony-fx3", nombre="Sony FX3")
        assert e.cantidad == 1
        assert e.visible_catalogo == 1
        assert e.estado == "ok"
        assert e.categorias == []
        assert e.etiquetas == []

    def test_con_m2m(self):
        e = schema.Equipo(
            slug="sony-fx3",
            nombre="Sony FX3",
            marca_nombre="Sony",
            categorias=[
                {"nombre": "Cinema Cameras", "orden": 1},
                {"nombre": "Montura E", "orden": 2},
            ],
            etiquetas=[
                {"nombre": "destacado", "origen": "manual", "orden": 0},
            ],
        )
        assert len(e.categorias) == 2
        assert e.categorias[0].nombre == "Cinema Cameras"
        assert e.etiquetas[0].origen == "manual"

    def test_origen_etiqueta_invalido(self):
        with pytest.raises(ValidationError):
            schema.Equipo(
                slug="sony-fx3", nombre="Sony FX3",
                etiquetas=[{"nombre": "x", "origen": "wat"}],
            )


class TestEquipoSpec:
    def test_basico(self):
        es = schema.EquipoSpec(
            equipo_slug="sony-fx3",
            spec_ref={"categoria_raiz_nombre": "Cámaras", "spec_key": "sensor"},
            value="Full Frame",
        )
        assert es.spec_ref.spec_key == "sensor"
        assert es.value == "Full Frame"


class TestEquipoFicha:
    def test_minimo(self):
        f = schema.EquipoFicha(equipo_slug="sony-fx3")
        assert f.descripcion is None

    def test_completo(self):
        f = schema.EquipoFicha(
            equipo_slug="sony-fx3",
            descripcion="Cinema camera",
            peso="640g",
            dimensiones="129x77x84mm",
            precio_bh_usd=3899.0,
        )
        assert f.precio_bh_usd == 3899.0


class TestEntityModels:
    def test_todas_las_entidades_tienen_modelo(self):
        from dataio.paths import ENTITY_ORDER

        for entity in ENTITY_ORDER:
            assert entity in schema.ENTITY_MODELS, f"Falta modelo para {entity}"
            model = schema.ENTITY_MODELS[entity]
            assert issubclass(model, schema._Base)
