"""Tests puros de `clientes/queries/identidad.py` — fuente única de
nombre_legal/direccion_legal (antes recompuesto por separado en
`routes/clientes.py`, `routes/cliente_portal/cuenta.py` y
`services/pedidos_enriquecimiento.py`)."""
import pytest

from clientes.queries.identidad import nombre_legal, direccion_legal, nombre_completo_cliente


pytestmark = pytest.mark.unit


class TestNombreLegal:
    def test_verificado_usa_renaper(self):
        c = {
            "nombre": "freya",
            "apellido": "-",
            "nombre_renaper": "Freya",
            "apellido_renaper": "Bustamante",
        }
        assert nombre_legal(c) == "Freya Bustamante"

    def test_no_verificado_cae_al_base(self):
        c = {"nombre": "Julio", "apellido": "Fernández", "nombre_renaper": None}
        assert nombre_legal(c) == "Julio Fernández"

    def test_sin_apellido_renaper(self):
        c = {"nombre": "x", "apellido": "y", "nombre_renaper": "Ana", "apellido_renaper": None}
        assert nombre_legal(c) == "Ana"

    def test_sin_nada_es_none_safe(self):
        # Cuenta liviana sin nombre/apellido cargados — el fallback NO debe
        # dar "None None" (bug del f"..." crudo que reemplazó
        # `nombre_completo_cliente`, que sí es None-safe).
        c = {"nombre": None, "apellido": None, "nombre_renaper": None}
        assert nombre_legal(c) == ""


class TestNombreCompletoCliente:
    def test_nombre_y_apellido(self):
        assert nombre_completo_cliente("Freya", "Bustamante") == "Freya Bustamante"

    def test_sin_apellido(self):
        assert nombre_completo_cliente("Freya", "") == "Freya"

    def test_ambos_none(self):
        assert nombre_completo_cliente(None, None) == ""


class TestDireccionLegal:
    def test_verificado_usa_renaper(self):
        c = {"direccion": "base", "direccion_renaper": "Luzuriaga 1268"}
        assert direccion_legal(c) == "Luzuriaga 1268"

    def test_no_verificado_cae_al_base(self):
        c = {"direccion": "Av. Colón 3450", "direccion_renaper": None}
        assert direccion_legal(c) == "Av. Colón 3450"

    def test_sin_nada(self):
        c = {"direccion": None, "direccion_renaper": None}
        assert direccion_legal(c) is None
