"""Tests del job de housekeeping de auth (`jobs/purgar_auth.py`). Las purgas ya
están testeadas contra Postgres real en `test_sessions.py`/`test_auth_magic.py`
(vía sus respectivos `purge_expired`); acá solo se ejerce el contrato del job:
llama a los dos, devuelve las cantidades, y no asume nada de sus internals.
"""
import pytest

import jobs.purgar_auth as job

pytestmark = pytest.mark.unit


def test_llama_a_las_dos_purgas_y_devuelve_las_cantidades(monkeypatch):
    monkeypatch.setattr(job.sessions_commands, "purge_expired", lambda: 3)
    monkeypatch.setattr(job.magic_commands, "purge_expired", lambda: 5)
    assert job.purgar_sesiones_y_challenges_expirados() == (3, 5)


def test_cero_no_rompe(monkeypatch):
    monkeypatch.setattr(job.sessions_commands, "purge_expired", lambda: 0)
    monkeypatch.setattr(job.magic_commands, "purge_expired", lambda: 0)
    assert job.purgar_sesiones_y_challenges_expirados() == (0, 0)
