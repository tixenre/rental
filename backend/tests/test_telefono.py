"""`services.telefono` — normalización/validación de teléfonos a E.164.

Puros (sin DB, sin red): `phonenumbers` es determinístico. Cubren los formatos
reales que aparecieron en el listado de talleres (con/sin +54, con `15`/celular)
y los casos borde (vacío, basura).
"""

from services import telefono


class TestNormalizar:
    def test_numeros_reales_del_listado_a_e164(self):
        # Los que se vieron sin normalizar en la tabla de inscripciones.
        assert telefono.normalizar("1131661693") == "+541131661693"
        assert telefono.normalizar("2236898641") == "+542236898641"
        assert telefono.normalizar("+542235766569") == "+542235766569"
        assert telefono.normalizar("2235444704") == "+542235444704"
        assert telefono.normalizar("2236329659") == "+542236329659"

    def test_tolera_separadores_y_espacios(self):
        assert telefono.normalizar("223 689 8641") == "+542236898641"
        assert telefono.normalizar("  2236898641  ") == "+542236898641"
        assert telefono.normalizar("223-689-8641") == "+542236898641"

    def test_celular_con_15_lleva_el_9_de_movil(self):
        # El `15` legacy → móvil → E.164 con el `9` que WhatsApp necesita.
        assert telefono.normalizar("011 15 3166-1693") == "+5491131661693"

    def test_ya_en_e164_es_idempotente(self):
        assert telefono.normalizar("+542236898641") == "+542236898641"

    def test_vacio_o_none_es_none(self):
        assert telefono.normalizar(None) is None
        assert telefono.normalizar("") is None
        assert telefono.normalizar("   ") is None

    def test_basura_es_none(self):
        assert telefono.normalizar("no soy un tel") is None
        assert telefono.normalizar("123") is None  # muy corto → inválido


class TestEsValido:
    def test_valido_e_invalido(self):
        assert telefono.es_valido("2236898641") is True
        assert telefono.es_valido("+542235766569") is True
        assert telefono.es_valido("123") is False
        assert telefono.es_valido("") is False
        assert telefono.es_valido(None) is False


class TestSoloDigitos:
    def test_saca_el_mas(self):
        assert telefono.solo_digitos("+542236898641") == "542236898641"

    def test_vacio_es_none(self):
        assert telefono.solo_digitos(None) is None
        assert telefono.solo_digitos("") is None


class TestFormatoDisplay:
    def test_valido_formato_nacional(self):
        # Formato nacional legible (no E.164) para mostrar.
        assert telefono.formato_display("2236898641") == "0223 689-8641"

    def test_invalido_cae_al_raw(self):
        assert telefono.formato_display("no soy un tel") == "no soy un tel"

    def test_vacio_es_none(self):
        assert telefono.formato_display(None) is None
        assert telefono.formato_display("  ") is None
