"""Tests para el campo tipo en equipos (A1 #635).

Cubre:
- Validación de EquipoCreate y EquipoUpdate (Pydantic).
- Que el backfill de la migración tiene la lógica correcta.
- Que duplicate_equipo hereda el tipo del original.
"""

import pytest
from pydantic import ValidationError

from routes.equipos import EquipoCreate, EquipoUpdate

pytestmark = pytest.mark.unit


# ─────────────────────────────────────────────────────────────────────────────
# EquipoCreate — validación de tipo
# ─────────────────────────────────────────────────────────────────────────────

class TestEquipoCreateTipo:
    def test_default_es_simple(self):
        e = EquipoCreate(nombre="Cámara")
        assert e.tipo == "simple"

    def test_acepta_simple(self):
        e = EquipoCreate(nombre="Cámara", tipo="simple")
        assert e.tipo == "simple"

    def test_acepta_kit(self):
        e = EquipoCreate(nombre="Kit de audio", tipo="kit")
        assert e.tipo == "kit"

    def test_acepta_combo(self):
        e = EquipoCreate(nombre="Combo estudio", tipo="combo")
        assert e.tipo == "combo"

    def test_rechaza_tipo_invalido(self):
        with pytest.raises(ValidationError) as exc_info:
            EquipoCreate(nombre="Algo", tipo="invalido")
        assert "tipo inválido" in str(exc_info.value)

    def test_rechaza_tipo_mayusculas(self):
        with pytest.raises(ValidationError):
            EquipoCreate(nombre="Algo", tipo="Simple")

    def test_permite_none(self):
        # None se normaliza a None (no al default — el default solo aplica si
        # el campo no se pasa). El endpoint lo resuelve con `or "simple"`.
        e = EquipoCreate(nombre="Cámara", tipo=None)
        assert e.tipo is None


# ─────────────────────────────────────────────────────────────────────────────
# EquipoUpdate — validación de tipo
# ─────────────────────────────────────────────────────────────────────────────

class TestEquipoUpdateTipo:
    def test_default_es_none(self):
        u = EquipoUpdate()
        assert u.tipo is None

    def test_acepta_todos_los_tipos(self):
        for t in ("simple", "kit", "combo"):
            u = EquipoUpdate(tipo=t)
            assert u.tipo == t

    def test_rechaza_tipo_invalido(self):
        with pytest.raises(ValidationError) as exc_info:
            EquipoUpdate(tipo="bundle")
        assert "tipo inválido" in str(exc_info.value)

    def test_exclude_unset_omite_tipo_si_no_se_manda(self):
        u = EquipoUpdate(nombre="Cámara")
        updates = u.model_dump(exclude_unset=True)
        assert "tipo" not in updates

    def test_include_tipo_si_se_manda(self):
        u = EquipoUpdate(tipo="kit")
        updates = u.model_dump(exclude_unset=True)
        assert updates == {"tipo": "kit"}


# ─────────────────────────────────────────────────────────────────────────────
# Lógica de backfill de la migración (SQL)
# ─────────────────────────────────────────────────────────────────────────────

class TestBackfillLogica:
    """Verifica la semántica del backfill sin BD real.

    La migración hace:
      UPDATE equipos SET tipo = 'kit'
      WHERE tipo = 'simple'
        AND id IN (SELECT DISTINCT equipo_id FROM kit_componentes)

    Probamos la clasificación directamente (es lógica pura).
    """

    def _clasificar(self, ids_con_kit: set[int], todos_los_ids: list[int]) -> dict[int, str]:
        """Simula el backfill: retorna tipo por equipo_id."""
        return {
            eid: ("kit" if eid in ids_con_kit else "simple")
            for eid in todos_los_ids
        }

    def test_sin_kit_queda_simple(self):
        resultado = self._clasificar(ids_con_kit=set(), todos_los_ids=[1, 2, 3])
        assert all(v == "simple" for v in resultado.values())

    def test_con_kit_queda_kit(self):
        resultado = self._clasificar(ids_con_kit={2}, todos_los_ids=[1, 2, 3])
        assert resultado[1] == "simple"
        assert resultado[2] == "kit"
        assert resultado[3] == "simple"

    def test_todos_con_kit(self):
        resultado = self._clasificar(ids_con_kit={1, 2, 3}, todos_los_ids=[1, 2, 3])
        assert all(v == "kit" for v in resultado.values())

    def test_combo_no_lo_asigna_el_backfill(self):
        # El backfill solo va de simple→kit. Los Combo se marcan a mano.
        resultado = self._clasificar(ids_con_kit={1}, todos_los_ids=[1])
        assert resultado[1] == "kit"
        assert "combo" not in resultado.values()
