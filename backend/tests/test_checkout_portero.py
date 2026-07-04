"""Candados del portero del checkout (`services.checkout.validar`).

Tests unitarios sin DB real: un _FakeConn configurable responde cada SELECT.
Cubre:
  1. Retorna listo=True cuando todo está OK.
  2. Retorna listo=False con TODOS los faltan en una sola pasada (fail-not-fast).
  3. Cada check falla independientemente.
  4. Los checks cableado-apagado (#1125, #1126) siempre retornan OK.
  5. TYC: ya_acepto / registrar_aceptacion son idempotentes.
  6. Carrito no encontrado → único falta de "carrito".
  7. Robustez (`_run_check`): un check que revienta con algo INESPERADO no
     tira abajo el resto del portero — se aísla, se loguea con contexto
     diagnosticable, y se trata fail-closed (bloquea) sin frenar a los
     checks que faltan correr.
"""

import datetime
import logging

from services.checkout.validar import (
    _Item,
    _check_carrito,
    _check_contacto,
    _check_fechas,
    _check_firma,
    _check_identidad,
    _check_precio,
    _check_stock_preflight,
    _check_tyc,
    _check_bloqueo,
    _check_antelacion,
    _date_str,
    _leer_carrito,
    _run_check,
    validar_checkout,
    faltan_firma_tyc,
)
from services.checkout.tyc import ya_acepto, registrar_aceptacion
from database import now_ar


# ── Fake infrastructure ────────────────────────────────────────────────────────


class _FakeCursor:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeConn:
    """Fake connection: devuelve respuestas pre-configuradas por query substring."""

    def __init__(self, responses: dict | None = None):
        self._resp = responses or {}
        self.executed = []

    def execute(self, sql: str, params=None):
        self.executed.append((sql, params))
        for key, val in self._resp.items():
            if key in sql:
                return _FakeCursor(val)
        return _FakeCursor(None)


def _conn_all_ok(items_json=None, tyc_accepted=True, email="test@example.com"):
    """Fake conn que pasa todos los checks sin problemas."""
    items = items_json or [{"equipo_id": 1, "cantidad": 1, "nombre": "Cámara"}]
    return _FakeConn({
        "carritos_activos": {
            "items_json": items,
            "fecha_desde": datetime.date.today() + datetime.timedelta(days=2),
            "fecha_hasta": datetime.date.today() + datetime.timedelta(days=5),
            "hora_desde": "09:00",
            "hora_hasta": "18:00",
        },
        "dni_validado_at": {"dni_validado_at": datetime.datetime.now()},
        "visible_catalogo": {"id": 1},
        "calcular_disponibilidad": None,  # se parchea más abajo si hace falta
        "precio_jornada": {"precio_jornada": 1000},
        "verified_contacts": {"value": email},
        "clientes WHERE id": {"email": email},
        "aceptaciones_tyc": {"cliente_id": 1} if tyc_accepted else None,
    })


# ── _date_str ──────────────────────────────────────────────────────────────────


def test_date_str_from_date():
    d = datetime.date(2026, 7, 10)
    assert _date_str(d) == "2026-07-10"


def test_date_str_from_str():
    assert _date_str("2026-07-10") == "2026-07-10"


def test_date_str_none():
    assert _date_str(None) is None


# ── _check_identidad ───────────────────────────────────────────────────────────


def test_check_identidad_ok():
    conn = _FakeConn({"dni_validado_at": {"dni_validado_at": datetime.datetime.now()}})
    faltan = []
    _check_identidad(conn, 1, faltan)
    assert faltan == []


def test_check_identidad_fail():
    conn = _FakeConn({"dni_validado_at": {"dni_validado_at": None}})
    faltan = []
    _check_identidad(conn, 1, faltan)
    assert len(faltan) == 1
    assert faltan[0]["check"] == "identidad"


# ── _check_carrito ─────────────────────────────────────────────────────────────


def test_check_carrito_ok():
    conn = _FakeConn({"visible_catalogo": {"id": 1}})
    faltan = []
    _check_carrito(conn, [_Item(1, 1)], faltan)
    assert faltan == []


def test_check_carrito_vacio():
    conn = _FakeConn({})
    faltan = []
    _check_carrito(conn, [], faltan)
    assert len(faltan) == 1
    assert faltan[0]["check"] == "carrito"
    assert "vacío" in faltan[0]["mensaje"]


def test_check_carrito_equipo_invisible():
    conn = _FakeConn({"visible_catalogo": None})  # None = no encontrado
    faltan = []
    _check_carrito(conn, [_Item(99, 1)], faltan)
    assert len(faltan) == 1
    assert faltan[0]["check"] == "carrito"


# ── _check_fechas ──────────────────────────────────────────────────────────────


def test_check_fechas_ok():
    hoy = datetime.date.today()
    faltan = []
    _check_fechas(
        str(hoy + datetime.timedelta(days=1)),
        str(hoy + datetime.timedelta(days=3)),
        False,
        faltan,
    )
    assert faltan == []


def test_check_fechas_sin_fecha():
    faltan = []
    _check_fechas(None, None, False, faltan)
    assert len(faltan) == 1
    assert faltan[0]["check"] == "fechas"


def test_check_fechas_hasta_menor_que_desde():
    hoy = datetime.date.today()
    faltan = []
    _check_fechas(
        str(hoy + datetime.timedelta(days=3)),
        str(hoy + datetime.timedelta(days=1)),
        False,
        faltan,
    )
    assert len(faltan) == 1
    assert "posterior" in faltan[0]["mensaje"]


# `now_ar().date()`, no `date.today()`: el portero compara contra hora de Argentina
# (validar.py: `d0 < now_ar().date()`). Con `date.today()` (UTC en CI) "ayer" cae en el
# MISMO día que AR entre las 00:00–03:00 UTC → falso negativo. Mismo reloj que el código.
def test_check_fechas_pasada_cliente():
    ayer = str(now_ar().date() - datetime.timedelta(days=1))
    manana = str(now_ar().date() + datetime.timedelta(days=1))
    faltan = []
    _check_fechas(ayer, manana, es_admin=False, faltan=faltan)
    assert len(faltan) == 1
    assert "pasado" in faltan[0]["mensaje"]


def test_check_fechas_pasada_admin_ok():
    ayer = str(now_ar().date() - datetime.timedelta(days=1))
    manana = str(now_ar().date() + datetime.timedelta(days=1))
    faltan = []
    _check_fechas(ayer, manana, es_admin=True, faltan=faltan)
    assert faltan == []


# ── faltan_firma_tyc (gate de creación, cliente-scoped, sin carrito) ──────────
# Reusa los MISMOS checks del portero (_check_tyc + _check_firma) → una sola fuente.


def test_faltan_firma_tyc_todo_ok():
    conn = _FakeConn({"aceptaciones_tyc": {"cliente_id": 1}})  # T&C aceptados
    assert faltan_firma_tyc(conn, cliente_id=1, firma_ok=True) == []


def test_faltan_firma_tyc_sin_firma():
    conn = _FakeConn({"aceptaciones_tyc": {"cliente_id": 1}})
    faltan = faltan_firma_tyc(conn, cliente_id=1, firma_ok=False)
    assert [f["check"] for f in faltan] == ["firma"]


def test_faltan_firma_tyc_sin_tyc():
    conn = _FakeConn({})  # aceptaciones_tyc → None → no aceptó
    faltan = faltan_firma_tyc(conn, cliente_id=1, firma_ok=True)
    assert [f["check"] for f in faltan] == ["tyc"]


def test_faltan_firma_tyc_sin_nada():
    conn = _FakeConn({})
    faltan = faltan_firma_tyc(conn, cliente_id=1, firma_ok=False)
    assert {f["check"] for f in faltan} == {"tyc", "firma"}


# ── _check_stock_preflight ────────────────────────────────────────────────────


def test_check_stock_preflight_ok(monkeypatch):
    monkeypatch.setattr(
        "services.checkout.validar.calcular_disponibilidad",
        lambda *a, **k: {"1": 5},
    )
    faltan = []
    _check_stock_preflight(_FakeConn(), [_Item(1, 2)], "2026-07-10", "2026-07-12", faltan)
    assert faltan == []


def test_check_stock_preflight_sin_stock(monkeypatch):
    monkeypatch.setattr(
        "services.checkout.validar.calcular_disponibilidad",
        lambda *a, **k: {"1": 0},
    )
    faltan = []
    _check_stock_preflight(_FakeConn(), [_Item(1, 2)], "2026-07-10", "2026-07-12", faltan)
    assert len(faltan) == 1
    assert faltan[0]["check"] == "stock"


# ── _check_precio ─────────────────────────────────────────────────────────────


def test_check_precio_ok(monkeypatch):
    monkeypatch.setattr(
        "services.checkout.validar.precios_catalogo_para_reserva",
        lambda *a, **k: {1: 1000},
    )
    faltan = []
    _check_precio(_FakeConn(), [_Item(1, 1)], faltan)
    assert faltan == []


def test_check_precio_fail(monkeypatch):
    from fastapi import HTTPException

    def raise_404(*a, **k):
        raise HTTPException(404, "no encontrado")

    monkeypatch.setattr("services.checkout.validar.precios_catalogo_para_reserva", raise_404)
    faltan = []
    _check_precio(_FakeConn(), [_Item(99, 1)], faltan)
    assert len(faltan) == 1
    assert faltan[0]["check"] == "precio"


# ── _check_contacto ────────────────────────────────────────────────────────────


def test_check_contacto_ok(monkeypatch):
    monkeypatch.setattr(
        "services.checkout.validar.email_comunicacion",
        lambda *a, **k: "test@example.com",
    )
    faltan = []
    _check_contacto(_FakeConn(), 1, faltan)
    assert faltan == []


def test_check_contacto_sin_email(monkeypatch):
    monkeypatch.setattr(
        "services.checkout.validar.email_comunicacion",
        lambda *a, **k: None,
    )
    faltan = []
    _check_contacto(_FakeConn(), 1, faltan)
    assert len(faltan) == 1
    assert faltan[0]["check"] == "contacto"


# ── _check_tyc ────────────────────────────────────────────────────────────────


def test_check_tyc_ok():
    conn = _FakeConn({"aceptaciones_tyc": {"cliente_id": 1, "version": "v1"}})
    faltan = []
    _check_tyc(conn, 1, faltan)
    assert faltan == []


def test_check_tyc_no_acepto():
    conn = _FakeConn({"aceptaciones_tyc": None})
    faltan = []
    _check_tyc(conn, 1, faltan)
    assert len(faltan) == 1
    assert faltan[0]["check"] == "tyc"


# ── _check_firma ──────────────────────────────────────────────────────────────


def test_check_firma_ok():
    faltan = []
    _check_firma(True, faltan)
    assert faltan == []


def test_check_firma_fail():
    faltan = []
    _check_firma(False, faltan)
    assert len(faltan) == 1
    assert faltan[0]["check"] == "firma"


# ── Cableado-apagado siempre OK ────────────────────────────────────────────────


def test_bloqueo_cableado_apagado():
    faltan = []
    _check_bloqueo(_FakeConn(), 1, faltan)
    assert faltan == []  # siempre OK hasta activar #1125


def test_antelacion_apagada_no_bloquea():
    # Setting en 0 (o ausente) → lead-time apagado: nunca bloquea.
    conn = _FakeConn({"app_settings": {"value": "0"}})
    faltan = []
    manana = (now_ar() + datetime.timedelta(days=1)).date().isoformat()
    _check_antelacion(conn, manana, "09:00", faltan)
    assert faltan == []


def test_antelacion_bloquea_dentro_de_la_ventana():
    # Lead-time 12h: un retiro dentro de las próximas 2h cae en la ventana → bloquea.
    conn = _FakeConn({"app_settings": {"value": "12"}})
    proximo = now_ar() + datetime.timedelta(hours=2)
    faltan = []
    _check_antelacion(conn, proximo.date().isoformat(), proximo.strftime("%H:%M"), faltan)
    assert len(faltan) == 1
    assert faltan[0]["check"] == "antelacion"


def test_antelacion_permite_fuera_de_la_ventana():
    # Lead-time 12h: un retiro dentro de 48h está fuera de la ventana → permite.
    conn = _FakeConn({"app_settings": {"value": "12"}})
    lejano = now_ar() + datetime.timedelta(hours=48)
    faltan = []
    _check_antelacion(conn, lejano.date().isoformat(), lejano.strftime("%H:%M"), faltan)
    assert faltan == []


# ── TYC helpers ───────────────────────────────────────────────────────────────


class _TycConn:
    """Fake conn específico para TYC con estado mutable."""

    def __init__(self):
        self._rows: list[tuple] = []

    def execute(self, sql, params=None):
        sql_lower = sql.lower()
        if "insert" in sql_lower:
            row = (params[0], params[1]) if params else None
            if row and row not in self._rows:
                self._rows.append(row)
            return _FakeCursor(None)
        if "select" in sql_lower and params:
            for r in self._rows:
                if r[0] == params[0] and r[1] == params[1]:
                    return _FakeCursor({"cliente_id": r[0], "version": r[1]})
        return _FakeCursor(None)


def test_ya_acepto_false_sin_registro():
    conn = _TycConn()
    assert ya_acepto(conn, 1) is False


def test_registrar_y_ya_acepto():
    conn = _TycConn()
    registrar_aceptacion(conn, 1)
    assert ya_acepto(conn, 1) is True


def test_registrar_idempotente():
    conn = _TycConn()
    registrar_aceptacion(conn, 1)
    registrar_aceptacion(conn, 1)  # segunda vez no debe romper
    assert len(conn._rows) == 1


# ── validar_checkout: camino feliz ────────────────────────────────────────────


def test_validar_checkout_listo(monkeypatch):
    """Cuando todo está OK el portero devuelve listo=True y faltan vacío."""
    monkeypatch.setattr(
        "services.checkout.validar.calcular_disponibilidad",
        lambda *a, **k: {"1": 5},
    )
    monkeypatch.setattr(
        "services.checkout.validar.precios_catalogo_para_reserva",
        lambda *a, **k: {1: 1000},
    )
    monkeypatch.setattr(
        "services.checkout.validar.email_comunicacion",
        lambda *a, **k: "test@example.com",
    )

    conn = _conn_all_ok()
    result = validar_checkout(conn, cliente_id=1, session_id="abc", firma_ok=True)
    assert result["listo"] is True
    assert result["faltan"] == []


# ── validar_checkout: carrito no encontrado ────────────────────────────────────


def test_validar_checkout_carrito_no_encontrado():
    conn = _FakeConn({"carritos_activos": None})
    result = validar_checkout(conn, cliente_id=1, session_id="abc", firma_ok=True)
    assert result["listo"] is False
    assert len(result["faltan"]) == 1
    assert result["faltan"][0]["check"] == "carrito"


def test_leer_carrito_no_filtra_por_confirmado():
    """Regresión: un cliente que ya armó UN pedido reusa el mismo `session_id`
    (persiste en localStorage) para el próximo — esa fila queda `confirmado=TRUE`
    (funnel del admin), pero el heartbeat le sigue refrescando items/fechas. Si
    `_leer_carrito` volviera a filtrar por `NOT confirmado`, el portero rompería
    con "No encontramos tu carrito" en cualquier segundo pedido de la sesión."""
    conn = _conn_all_ok()
    carrito = _leer_carrito(conn, session_id="abc", cliente_id=1)
    assert carrito is not None
    sql_carrito = [sql for sql, _ in conn.executed if "carritos_activos" in sql][0]
    assert "confirmado" not in sql_carrito


# ── validar_checkout: all checks fail (fail-not-fast) ─────────────────────────


def test_validar_checkout_fail_not_fast(monkeypatch):
    """Cuando todo falla, el portero devuelve TODOS los problemas, no solo el primero."""
    hoy = datetime.date.today()
    conn = _FakeConn({
        "carritos_activos": {
            "items_json": [{"equipo_id": 1, "cantidad": 1}],
            "fecha_desde": hoy + datetime.timedelta(days=2),
            "fecha_hasta": hoy + datetime.timedelta(days=5),
            "hora_desde": "09:00",
            "hora_hasta": "18:00",
        },
        "dni_validado_at": {"dni_validado_at": None},       # identidad falla
        "visible_catalogo": {"id": 1},                      # carrito OK
        "aceptaciones_tyc": None,                           # tyc falla
        "clientes WHERE id": {"email": None},               # contacto falla
        "verified_contacts": None,
    })
    monkeypatch.setattr(
        "services.checkout.validar.calcular_disponibilidad",
        lambda *a, **k: {"1": 5},
    )
    monkeypatch.setattr(
        "services.checkout.validar.precios_catalogo_para_reserva",
        lambda *a, **k: {1: 1000},
    )
    monkeypatch.setattr(
        "services.checkout.validar.email_comunicacion",
        lambda *a, **k: None,  # contacto falla
    )

    result = validar_checkout(conn, cliente_id=1, session_id="abc", firma_ok=False)
    assert result["listo"] is False

    checks = {f["check"] for f in result["faltan"]}
    assert "identidad" in checks
    assert "tyc" in checks
    assert "contacto" in checks
    assert "firma" in checks
    # Al menos 4 checks fallaron
    assert len(result["faltan"]) >= 4


# ── Robustez: un check que revienta no tira abajo el portero ─────────────────


def test_run_check_aisla_excepcion_inesperada_y_bloquea(caplog):
    def _explota(conn, cliente_id, faltan):
        raise RuntimeError("boom — bug interno del check")

    faltan: list[dict] = []
    with caplog.at_level(logging.ERROR):
        _run_check("mi_check", 42, "sess-1", _explota, None, 42, faltan=faltan)

    assert len(faltan) == 1
    assert faltan[0]["check"] == "mi_check"
    # Fail-closed: se agrega un faltante, no se deja pasar en silencio.
    assert faltan[0]["mensaje"]
    # Se logueó con el nombre del check + cliente_id/session_id (diagnosticable).
    assert any("mi_check" in r.message for r in caplog.records)
    assert any("42" in r.message for r in caplog.records)
    assert any("sess-1" in r.message for r in caplog.records)


def test_run_check_no_interfiere_con_la_falla_de_negocio_normal():
    """Un check que agrega su propio `_falta` (camino normal, sin excepción)
    no debe verse alterado por el wrapper de aislamiento."""
    faltan: list[dict] = []
    _run_check("identidad", 1, "abc", _check_identidad, _FakeConn({"dni_validado_at": None}), 1, faltan=faltan)
    assert len(faltan) == 1
    assert faltan[0]["check"] == "identidad"
    assert "verificar tu identidad" in faltan[0]["mensaje"]


def test_validar_checkout_check_roto_no_frena_a_los_demas(monkeypatch):
    """Si UN check revienta con algo inesperado, los checks que corren
    DESPUÉS en la secuencia siguen ejecutándose (fail-not-fast se mantiene
    incluso ante una falla inesperada, no solo ante faltantes de negocio)."""
    monkeypatch.setattr(
        "services.checkout.validar._check_stock_preflight",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("stock explotó")),
    )
    monkeypatch.setattr(
        "services.checkout.validar.precios_catalogo_para_reserva",
        lambda *a, **k: {1: 1000},
    )
    monkeypatch.setattr(
        "services.checkout.validar.email_comunicacion",
        lambda *a, **k: None,  # contacto falla también — debe seguir corriendo
    )

    conn = _conn_all_ok()
    result = validar_checkout(conn, cliente_id=1, session_id="abc", firma_ok=True)

    assert result["listo"] is False
    checks = {f["check"] for f in result["faltan"]}
    # El check roto aparece como faltante (fail-closed)...
    assert "stock" in checks
    # ...y el check que corre DESPUÉS en la secuencia (contacto) igual se ejecutó.
    assert "contacto" in checks


def test_validar_checkout_carrito_corrupto_no_500ea():
    """`items_json` con una forma inesperada (no lista de dicts con equipo_id)
    no debe tirar un 500 crudo — se trata como carrito en mal estado."""
    conn = _FakeConn({
        "carritos_activos": {
            "items_json": "no es json válido {{{",
            "fecha_desde": datetime.date.today() + datetime.timedelta(days=2),
            "fecha_hasta": datetime.date.today() + datetime.timedelta(days=5),
            "hora_desde": "09:00",
            "hora_hasta": "18:00",
        },
    })
    result = validar_checkout(conn, cliente_id=1, session_id="abc", firma_ok=True)
    assert result["listo"] is False
    assert result["faltan"][0]["check"] == "carrito"
