"""Tests del motor de magic-link single-use (auth/queries|commands/magic.py).

El signer es real (firma/verifica de verdad); la conexión es un fake que controla qué
devuelve el UPDATE…RETURNING (la fila = nonce sin usar; None = ya usado/vencido).
"""
import pytest

from auth.queries import magic as magic_queries
from auth.commands import magic as magic_commands

pytestmark = pytest.mark.unit


class _Cur:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _Conn:
    """Fake: graba execute(); el UPDATE…RETURNING devuelve fila (sin usar) o None (usado)."""

    def __init__(self, update_row=True):
        self.update_row = update_row
        self.calls = []

    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        self.calls.append((s, tuple(params)))
        if s.startswith("UPDATE auth_challenges"):
            return _Cur({"id": 1} if self.update_row else None)
        if s.startswith("SELECT 1 FROM auth_challenges"):  # peek
            return _Cur({"x": 1} if self.update_row else None)
        return _Cur(None)

    def commit(self):
        pass

    def close(self):
        pass


def _sql(c, needle):
    return [x for x in c.calls if needle in x[0]]


def test_crear_y_consumir_roundtrip():
    c = _Conn()
    token = magic_commands.crear(email="A@B.com", purpose="invitacion", cliente_id=7, conn=c)
    ins = _sql(c, "INSERT INTO auth_challenges")
    assert ins and ins[0][1][0] == "a@b.com"  # email normalizado a lower
    # Consumir con el MISMO purpose → devuelve el contexto firmado (cid + email).
    c2 = _Conn(update_row=True)
    assert magic_commands.consumir(token, purpose="invitacion", conn=c2) == {"cliente_id": 7, "email": "a@b.com"}
    assert _sql(c2, "UPDATE auth_challenges")  # marcó usado (single-use)


def test_peek_valida_sin_consumir():
    token = magic_commands.crear(email="a@b.com", purpose="invitacion", cliente_id=3, conn=_Conn())
    c = _Conn(update_row=True)  # el SELECT de peek matchea (fila sin usar)
    assert magic_queries.peek(token, purpose="invitacion", conn=c) == {"cliente_id": 3, "email": "a@b.com"}
    assert _sql(c, "SELECT 1 FROM auth_challenges")  # leyó…
    assert not _sql(c, "UPDATE")  # …NO consumió


def test_consumir_purpose_distinto_no_toca_la_tabla():
    c = _Conn()
    token = magic_commands.crear(email="a@b.com", purpose="invitacion", cliente_id=7, conn=c)
    c2 = _Conn(update_row=True)
    assert magic_commands.consumir(token, purpose="recuperacion", conn=c2) is None
    assert not _sql(c2, "UPDATE")  # purpose distinto → ni intenta consumir


def test_consumir_ya_usado_devuelve_none():
    c = _Conn()
    token = magic_commands.crear(email="a@b.com", purpose="invitacion", cliente_id=7, conn=c)
    # UPDATE no matchea (used_at ya seteado / vencido) → None, no resuelve el contexto.
    assert magic_commands.consumir(token, purpose="invitacion", conn=_Conn(update_row=False)) is None


def test_consumir_token_forjado_devuelve_none():
    # Sin firma válida no se llega ni a la tabla.
    c = _Conn(update_row=True)
    assert magic_commands.consumir("basura.no.firmada", purpose="invitacion", conn=c) is None
    assert not _sql(c, "UPDATE")
