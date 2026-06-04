"""Tests del job de recordatorios de retiro (`jobs/recordatorios.py`) y del
gating del scheduler in-process (`jobs/scheduler.py`).

La consulta SQL real (filtrar por estado/fecha/NOT EXISTS) se prueba a nivel
Postgres en otro lado; acá se aísla la lógica del job con un conn fake que
devuelve los pedidos candidatos, y se verifica el ruteo a `send_email`, el
conteo del resumen y el modo `dry_run`. El envío real (idempotencia vía índice
único) es responsabilidad de `services.email`, ya cubierto en su propio test.
"""

from datetime import datetime

import pytest

import jobs.recordatorios as rec
import jobs.scheduler as sched

pytestmark = pytest.mark.unit


# ── Fakes ────────────────────────────────────────────────────────────────────

class FakeRow(dict):
    pass


class FakeCursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class FakeJobConn:
    """Conn que sirve el barrido de pedidos y deja vacíos los items."""

    def __init__(self, pedidos):
        self._pedidos = pedidos
        self.closed = False

    def execute(self, sql, params=()):
        s = " ".join(sql.split()).upper()
        if "FROM ALQUILERES A" in s and "NOT EXISTS" in s:
            return FakeCursor([FakeRow(**p) for p in self._pedidos])
        if "FROM ALQUILER_ITEMS" in s:
            return FakeCursor([])  # sin items → contexto con items vacíos
        return FakeCursor([])

    def close(self):
        self.closed = True


HOY = datetime(2026, 6, 4, 10, 0, 0)


def _pedido(**over):
    base = dict(
        id=1, numero_pedido=1001, cliente_nombre="Juana",
        cliente_email="juana@x.com", cliente_telefono="099",
        fecha_desde=datetime(2026, 6, 5, 10, 0), fecha_hasta=datetime(2026, 6, 6, 18, 0),
        monto_total=12500, notas="",
    )
    base.update(over)
    return base


@pytest.fixture
def capture_send(monkeypatch):
    """Reemplaza send_email por un stub que registra llamadas."""
    calls = []

    def fake_send(template_key, to, context, alquiler_id=None):
        calls.append((template_key, to, alquiler_id, context))
        return {"ok": True, "provider": "test", "log_id": len(calls)}

    monkeypatch.setattr(rec, "send_email", fake_send)
    return calls


# ── Job: envío real ──────────────────────────────────────────────────────────

class TestEnviar:
    def test_manda_uno_por_pedido_y_cuenta(self, capture_send):
        conn = FakeJobConn([_pedido(id=1), _pedido(id=2, numero_pedido=1002,
                                                   cliente_email="b@x.com")])
        res = rec.enviar_recordatorios_retiro(conn, hoy=HOY)
        assert res["candidatos"] == 2
        assert res["enviados"] == 2
        assert res["fallidos"] == 0
        assert len(capture_send) == 2
        # Usa el template correcto y el id del pedido como alquiler_id.
        assert capture_send[0][0] == "recordatorio_retiro"
        assert capture_send[0][2] == 1

    def test_contexto_trae_variables_del_template(self, capture_send):
        conn = FakeJobConn([_pedido(numero_pedido=1234)])
        rec.enviar_recordatorios_retiro(conn, hoy=HOY)
        ctx = capture_send[0][3]
        assert ctx["numero_pedido"] == 1234
        assert ctx["cliente_nombre"] == "Juana"
        assert "portal_url" in ctx and "fecha_desde" in ctx

    def test_fecha_retiro_es_manana(self, capture_send):
        conn = FakeJobConn([])
        res = rec.enviar_recordatorios_retiro(conn, hoy=HOY)
        assert res["fecha_retiro"] == "2026-06-05"
        assert res["candidatos"] == 0
        assert capture_send == []

    def test_send_fallido_se_contabiliza_sin_propagar(self, monkeypatch):
        monkeypatch.setattr(
            rec, "send_email",
            lambda *a, **k: {"ok": False, "error": "boom"},
        )
        conn = FakeJobConn([_pedido()])
        res = rec.enviar_recordatorios_retiro(conn, hoy=HOY)
        assert res["enviados"] == 0 and res["fallidos"] == 1
        assert res["pedidos"][0]["status"] == "failed"
        assert res["pedidos"][0]["error"] == "boom"

    def test_conn_propia_se_cierra(self, capture_send, monkeypatch):
        conn = FakeJobConn([_pedido()])
        monkeypatch.setattr(rec, "get_db", lambda: conn)
        rec.enviar_recordatorios_retiro(hoy=HOY)  # sin conn → la abre y cierra
        assert conn.closed is True

    def test_conn_ajena_no_se_cierra(self, capture_send):
        conn = FakeJobConn([_pedido()])
        rec.enviar_recordatorios_retiro(conn, hoy=HOY)
        assert conn.closed is False


# ── Job: dry_run ─────────────────────────────────────────────────────────────

class TestDryRun:
    def test_no_manda_nada(self, capture_send):
        conn = FakeJobConn([_pedido(id=1), _pedido(id=2)])
        res = rec.enviar_recordatorios_retiro(conn, hoy=HOY, dry_run=True)
        assert res["dry_run"] is True
        assert res["candidatos"] == 2
        assert res["enviados"] == 0 and res["fallidos"] == 0
        assert capture_send == []  # send_email jamás se llamó
        assert all(p["status"] == "dry_run" for p in res["pedidos"])


# ── Scheduler: gating por entorno ────────────────────────────────────────────

class TestSchedulerGating:
    def test_apagado_por_default(self, monkeypatch):
        monkeypatch.delenv("REMINDERS_ENABLED", raising=False)
        started = {"n": 0}
        monkeypatch.setattr(sched.threading, "Thread",
                            lambda *a, **k: pytest.fail("no debía arrancar"))
        assert sched.start_scheduler() is False

    @pytest.mark.parametrize("val", ["1", "true", "YES"])
    def test_prende_con_flag(self, monkeypatch, val):
        monkeypatch.setenv("REMINDERS_ENABLED", val)

        class FakeThread:
            def __init__(self, *a, **k):
                self.started = False

            def start(self):
                self.started = True

        monkeypatch.setattr(sched.threading, "Thread", FakeThread)
        assert sched.start_scheduler() is True

    def test_flag_invalido_no_prende(self, monkeypatch):
        monkeypatch.setenv("REMINDERS_ENABLED", "nope")
        assert sched._enabled() is False
