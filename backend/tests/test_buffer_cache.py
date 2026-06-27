"""Cache del buffer global (`buffer_horas_alquiler`) del motor de reservas.

`get_buffer_horas` cachea a nivel proceso para no pegarle a `app_settings` en
cada chequeo de disponibilidad/confirmación. Estos tests fijan que:
  - el segundo acceso NO vuelve a la DB (sirve el cacheado),
  - `invalidate_buffer_cache` fuerza recargar (lo usa el writer de settings),
  - el TTL expira y recarga solo (red de seguridad multi-worker).

El fixture autouse `_reset_buffer_cache` (conftest) ya invalida antes de cada
test, así que cada caso arranca con el cache frío.
"""
import pytest

from reservas import get_buffer_horas, invalidate_buffer_cache
import reservas.semantics as semantics

pytestmark = pytest.mark.unit


class FakeRow(dict):
    pass


class FakeCursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _SettingsConn:
    """FakeConn que cuenta cuántas veces se leyó `app_settings` y deja cambiar
    el valor devuelto, para simular que el admin actualizó el buffer."""

    def __init__(self, valor=0):
        self.valor = valor
        self.lecturas = 0

    def execute(self, sql, params=()):
        s = " ".join(sql.split()).upper()
        if "FROM APP_SETTINGS WHERE KEY = %S" in s:
            self.lecturas += 1
            return FakeCursor([FakeRow(value=str(self.valor))])
        return FakeCursor([])


def test_segunda_lectura_sirve_del_cache():
    conn = _SettingsConn(valor=3)
    assert get_buffer_horas(conn) == 3
    assert get_buffer_horas(conn) == 3
    # La segunda llamada NO vuelve a la DB.
    assert conn.lecturas == 1


def test_invalidate_fuerza_recarga():
    conn = _SettingsConn(valor=2)
    assert get_buffer_horas(conn) == 2
    assert conn.lecturas == 1

    # El admin cambia el buffer → el writer invalida → la próxima lectura ve el nuevo.
    conn.valor = 9
    invalidate_buffer_cache()
    assert get_buffer_horas(conn) == 9
    assert conn.lecturas == 2


def test_ttl_vencido_recarga(monkeypatch):
    conn = _SettingsConn(valor=4)
    # Tiempo controlado para no depender del reloj real.
    reloj = {"t": 1000.0}
    monkeypatch.setattr(semantics.time, "monotonic", lambda: reloj["t"])

    assert get_buffer_horas(conn) == 4
    assert conn.lecturas == 1

    # Dentro del TTL: sigue cacheado.
    reloj["t"] += semantics._BUFFER_TTL_SEG - 1
    assert get_buffer_horas(conn) == 4
    assert conn.lecturas == 1

    # Pasado el TTL: recarga sola.
    reloj["t"] += 2
    conn.valor = 7
    assert get_buffer_horas(conn) == 7
    assert conn.lecturas == 2


def test_valor_invalido_o_ausente_devuelve_cero():
    # Sin fila → 0.
    class _Vacio:
        def execute(self, sql, params=()):
            return FakeCursor([])

    assert get_buffer_horas(_Vacio()) == 0

    invalidate_buffer_cache()
    # Valor no numérico → 0 (defensivo).
    conn = _SettingsConn(valor="abc")
    assert get_buffer_horas(conn) == 0
