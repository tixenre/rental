"""Tests puros de `services.facturacion.wsaa_cache._vigente`.

Sin test dedicado pese a ser el borde exacto que decide si se renueva el TA contra WSAA o se
reusa el cacheado (hallazgo de la auditoría cruzada de la librería `arca_fe`, 2026-07-04).
`get_ta` en sí (el flujo completo con `conn`/WSAA real) ya se ejercita indirectamente en
`test_facturacion_engine.py`; acá se aísla el predicado puro."""
from datetime import datetime, timedelta, timezone

from services.facturacion.wsaa_cache import _MARGEN_MINUTOS, _vigente


def test_vigente_none_no_es_vigente():
    """Sin TA cacheado (columna NULL) → renovar, no explotar."""
    limite = datetime.now(timezone.utc) + timedelta(minutes=_MARGEN_MINUTOS)
    assert _vigente(None, limite) is False


def test_vigente_justo_en_el_margen_no_es_vigente():
    """`expira_at == limite` (el TA vence EXACTAMENTE cuando termina el margen de gracia) —
    borde estricto: `>` no `>=`, se trata como vencido (renueva un poco antes de lo justo,
    nunca un poco después)."""
    ahora = datetime.now(timezone.utc)
    limite = ahora + timedelta(minutes=_MARGEN_MINUTOS)
    assert _vigente(limite, limite) is False


def test_vigente_un_segundo_despues_del_margen_es_vigente():
    ahora = datetime.now(timezone.utc)
    limite = ahora + timedelta(minutes=_MARGEN_MINUTOS)
    expira_at = limite + timedelta(seconds=1)
    assert _vigente(expira_at, limite) is True


def test_vigente_ya_vencido_no_es_vigente():
    ahora = datetime.now(timezone.utc)
    limite = ahora + timedelta(minutes=_MARGEN_MINUTOS)
    expira_at = ahora - timedelta(minutes=5)
    assert _vigente(expira_at, limite) is False


def test_vigente_naive_datetime_se_asume_utc():
    """Postgres puede devolver un `datetime` naive (sin tzinfo) si la columna no fuera
    `TIMESTAMPTZ` — `_vigente` lo asume UTC en vez de reventar con un `TypeError` al comparar
    naive vs. aware."""
    ahora = datetime.now(timezone.utc)
    limite = ahora + timedelta(minutes=_MARGEN_MINUTOS)
    expira_at_naive = (limite + timedelta(hours=1)).replace(tzinfo=None)
    assert _vigente(expira_at_naive, limite) is True
