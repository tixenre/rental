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
        assert e.estado == "operativo"
        assert e.categorias == []

    def test_con_m2m(self):
        e = schema.Equipo(
            slug="sony-fx3",
            nombre="Sony FX3",
            marca_nombre="Sony",
            categorias=[
                {"nombre": "Cinema Cameras", "orden": 1},
                {"nombre": "Montura E", "orden": 2},
            ],
        )
        assert len(e.categorias) == 2
        assert e.categorias[0].nombre == "Cinema Cameras"

    def test_rechaza_campos_extra(self):
        # El sistema de etiquetas (tags libres) se eliminó (#1163 F5) — un
        # JSON viejo que aún traiga la clave debe rechazarse, no ignorarse.
        with pytest.raises(ValidationError):
            schema.Equipo(
                slug="sony-fx3", nombre="Sony FX3",
                etiquetas=[{"nombre": "x", "origen": "manual"}],
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
        # Fase F: peso/dimensiones migraron a equipo_specs. EquipoFicha ya
        # no las acepta — solo descripcion/notas/keywords/multimedia.
        f = schema.EquipoFicha(
            equipo_slug="sony-fx3",
            descripcion="Cinema camera",
            notas="Sin tarjetas",
            precio_bh_usd=3899.0,
            fuente_url="https://bhphotovideo.com/...",
        )
        assert f.precio_bh_usd == 3899.0


class TestEntityModels:
    def test_todas_las_entidades_tienen_modelo(self):
        from dataio.paths import ENTITY_ORDER

        for entity in ENTITY_ORDER:
            assert entity in schema.ENTITY_MODELS, f"Falta modelo para {entity}"
            model = schema.ENTITY_MODELS[entity]
            assert issubclass(model, schema._Base)


class TestCliente:
    def test_minimo(self):
        c = schema.Cliente(email="x@y.com", nombre="X", apellido="Y")
        assert c.descuento == 0.0
        assert c.perfil_impuestos == "consumidor_final"
        assert c.supabase_uid is None

    def test_completo(self):
        c = schema.Cliente(
            email="x@y.com", nombre="X", apellido="Y",
            cuit="20-12345678-9", descuento=15.5,
            razon_social="X SA", domicilio_fiscal="Av Y 1",
            supabase_uid="123e4567-e89b-12d3-a456-426614174000",
        )
        assert c.descuento == 15.5
        assert c.supabase_uid == "123e4567-e89b-12d3-a456-426614174000"

    def test_rechaza_sin_email(self):
        with pytest.raises(ValidationError):
            schema.Cliente(nombre="X", apellido="Y")


class TestAlquiler:
    def test_minimo(self):
        a = schema.Alquiler(
            numero_pedido=1234,
            cliente_nombre="Juan",
            fecha_desde="2026-01-01",
            fecha_hasta="2026-01-03",
        )
        assert a.estado == "solicitado"
        assert a.monto_total == 0
        assert a.items == []
        assert a.pagos == []

    def test_con_items_y_pagos(self):
        a = schema.Alquiler(
            numero_pedido=1234,
            cliente_email="x@y.com",
            cliente_nombre="X Y",
            fecha_desde="2026-01-01",
            fecha_hasta="2026-01-03",
            monto_total=50000,
            items=[
                {"equipo_slug": "sony-fx3", "cantidad": 1, "precio_jornada": 15000, "subtotal": 30000},
                {"equipo_slug": "canon-r5", "cantidad": 2, "precio_jornada": 10000, "subtotal": 40000},
            ],
            pagos=[
                {"monto": 25000, "concepto": "seña", "fecha": "2025-12-20"},
            ],
        )
        assert len(a.items) == 2
        assert a.items[0].equipo_slug == "sony-fx3"
        assert a.items[1].cantidad == 2
        assert len(a.pagos) == 1
        assert a.pagos[0].concepto == "seña"

    def test_rechaza_sin_numero_pedido(self):
        with pytest.raises(ValidationError):
            schema.Alquiler(
                cliente_nombre="X",
                fecha_desde="2026-01-01",
                fecha_hasta="2026-01-03",
            )
