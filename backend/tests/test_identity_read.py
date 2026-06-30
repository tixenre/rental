"""Tests del lector único get_validated_identity — FakeConn que enruta por SQL.

Valida la derivación del estado (no_verificado / verificado / conflicto), el gating
de la identidad legal (no se expone sin verificar) y la preferencia de contacto
(Google → Didit). Sin DB real (la integración va aparte, opt-in).
"""
import pytest

from identity import get_validated_identity

pytestmark = pytest.mark.unit


class _Cur:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row

    def fetchall(self):
        return []


class _RoutingConn:
    """Conn fake que enruta por contenido del SQL — devuelve filas canned para el
    SELECT principal de clientes y para las queries de email/teléfono."""

    def __init__(self, *, cliente, email_contact=None, phone_contact=None):
        self.cliente = cliente
        self.email_contact = email_contact  # fila verified_contacts kind=email (o None)
        self.phone_contact = phone_contact

    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        if "FROM verified_contacts" in s and "kind='email'" in s:
            return _Cur(self.email_contact)
        if "FROM verified_contacts" in s and "kind='phone'" in s:
            return _Cur(self.phone_contact)
        if "SELECT email FROM clientes" in s:
            return _Cur({"email": (self.cliente or {}).get("email")})
        if "SELECT telefono FROM clientes" in s:
            return _Cur({"telefono": (self.cliente or {}).get("telefono")})
        return _Cur(self.cliente)  # el SELECT principal

    def close(self):
        pass


def _identidad(**kw):
    return get_validated_identity(1, conn=_RoutingConn(**kw))


def test_verificado_devuelve_identidad_legal():
    vi = _identidad(cliente={
        "id": 1, "dni_validado_at": "2026-06-29T12:00:00", "identidad_conflicto": False,
        "dni_verificacion_estado": "verificado",
        "nombre_renaper": "Juan", "apellido_renaper": "Pérez",
        "nombre_completo_renaper": "Juan Carlos Pérez", "dni": "12345678",
        "cuil": "20123456786", "fecha_nacimiento_renaper": "1990-05-15",
        "direccion_renaper": "Av. Corrientes 1234", "email": "juan@gmail.com",
    })
    assert vi.estado == "verificado" and vi.verificado is True
    assert vi.nombre_legal == "Juan Carlos Pérez"
    assert vi.cuil == "20123456786"
    assert vi.direccion == "Av. Corrientes 1234"  # alimenta el contrato
    assert vi.email == "juan@gmail.com"  # Google (base), preferido


def test_no_verificado_no_inventa_identidad():
    vi = _identidad(cliente={
        "id": 1, "dni_validado_at": None, "identidad_conflicto": False,
        "dni_verificacion_estado": "no_verificado",
        "nombre_renaper": None, "email": "liviana@gmail.com",
    })
    assert vi.estado == "no_verificado" and vi.verificado is False
    assert vi.nombre_legal is None and vi.cuil is None and vi.dni is None
    assert vi.email == "liviana@gmail.com"  # el contacto sí está (desde el alta)


def test_conflicto_no_expone_identidad():
    vi = _identidad(cliente={
        "id": 1, "dni_validado_at": "2026-06-29T12:00:00", "identidad_conflicto": True,
        "dni_verificacion_estado": "verificado", "cuil": "20123456786", "email": "x@y.com",
    })
    assert vi.estado == "conflicto"  # gana aunque esté validado → necesita mano del admin
    assert vi.verificado is False
    assert vi.cuil is None  # no expone identidad legal en conflicto


def test_email_fallback_a_didit_si_passkey_only():
    vi = _identidad(
        cliente={"id": 1, "dni_validado_at": None, "identidad_conflicto": False, "email": None},
        email_contact={"value": "didit@verificado.com"},
    )
    assert vi.email == "didit@verificado.com"  # sin Google → fallback al de Didit


def test_telefono_prefiere_verificado():
    vi = _identidad(
        cliente={"id": 1, "dni_validado_at": None, "identidad_conflicto": False,
                 "email": "a@b.com", "telefono": "viejo"},
        phone_contact={"value": "+5492235551234"},
    )
    assert vi.telefono == "+5492235551234"  # E.164 verificado preferido sobre el base


def test_cliente_inexistente_devuelve_none():
    assert get_validated_identity(99, conn=_RoutingConn(cliente=None)) is None
