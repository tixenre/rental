"""Tests para la iniciativa de completitud de catálogo (#1051).

Cubre:
- Stream A: 7mo slot `specs` en /inventario/calidad.
- Stream C: import CSV de inventario con dry-run.
"""

import csv
import io

import pytest

from dataio.csv_importers import CSVImportError, import_inventario_csv

pytestmark = pytest.mark.unit


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_csv(*rows: dict) -> bytes:
    """Arma un CSV UTF-8 con BOM a partir de dicts.

    Las columnas son la unión de todas las keys (orden de la primera fila).
    """
    if not rows:
        return b""
    seen: dict[str, None] = {}
    for r in rows:
        for k in r:
            seen.setdefault(k, None)
    cols = list(seen)
    buf = io.StringIO()
    buf.write("﻿")  # BOM
    writer = csv.DictWriter(buf, fieldnames=cols)
    writer.writeheader()
    for r in rows:
        writer.writerow({c: r.get(c, "") for c in cols})
    return buf.getvalue().encode("utf-8")


class _FakeCursorMany:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeConn:
    """Simula una conexión de BD con estado mutable (equipos dict)."""

    def __init__(self, equipos: list[dict]):
        # equipos es lista de {id, serie, valor_reposicion, bh_url, fecha_compra}
        self._equipos: dict[int, dict] = {e["id"]: dict(e) for e in equipos}
        self._executed: list[tuple] = []
        self.committed = False

    def execute(self, sql: str, params=None):
        sql_l = sql.lower().strip()
        if sql_l.startswith("select"):
            # Simular la query de estado actual
            ids = list(params) if params else []
            rows = [self._equipos[i] for i in ids if i in self._equipos]
            return _FakeCursorMany(rows)
        if sql_l.startswith("update equipos"):
            # Registrar la update sin aplicar (dry-run ya lo controla el importer)
            self._executed.append((sql, params))
            return None
        return _FakeCursorMany([])

    def commit(self):
        self.committed = True


# ── Stream A: 7mo slot specs ───────────────────────────────────────────────────

def _read_source(rel_path: str) -> str:
    """Lee el source de un archivo backend relativo al directorio actual."""
    from pathlib import Path
    return (Path(__file__).parent.parent / rel_path).read_text(encoding="utf-8")


def test_calidad_respuesta_incluye_specs():
    """Verificar que el módulo inventario construye la key 'specs' en faltantes."""
    src = _read_source("routes/inventario.py")
    assert '"specs"' in src or "'specs'" in src, (
        "get_calidad_inventario debe incluir la key 'specs' en faltantes"
    )
    assert "sin_specs" in src, (
        "get_calidad_inventario debe contar equipos sin specs (sin_specs)"
    )
    assert "equipo_specs" in src, (
        "el conteo de sin_specs debe usar la tabla equipo_specs"
    )


def test_falta_sql_includes_specs():
    """FALTA_SQL en equipos/core.py debe tener la clave 'specs'."""
    src = _read_source("routes/equipos/core.py")
    assert '"specs"' in src, "FALTA_SQL debe incluir clave 'specs'"
    assert "equipo_specs" in src, "El filtro de specs debe usar la tabla equipo_specs"


# ── Stream C: CSV import inventario ───────────────────────────────────────────

def test_import_dry_run_no_commit():
    """dry_run=True no debe commitear."""
    conn = _FakeConn([
        {"id": 1, "serie": None, "valor_reposicion": None, "bh_url": None, "fecha_compra": None}
    ])
    raw = _make_csv({"id": "1", "serie": "SN-001"})
    result = import_inventario_csv(conn, raw, dry_run=True)
    assert result["dry_run"] is True
    assert not conn.committed
    assert result["actualizados"] == 1
    assert len(result["diff"]) == 1
    assert result["diff"][0] == {"id": 1, "campo": "serie", "antes": None, "despues": "SN-001"}


def test_import_apply_commits():
    """dry_run=False debe commitear."""
    conn = _FakeConn([
        {"id": 2, "serie": None, "valor_reposicion": None, "bh_url": None, "fecha_compra": None}
    ])
    raw = _make_csv({"id": "2", "serie": "SN-002", "valor_reposicion": "15000"})
    result = import_inventario_csv(conn, raw, dry_run=False)
    assert result["dry_run"] is False
    assert conn.committed
    assert result["actualizados"] == 1


def test_import_sin_cambio_no_diff():
    """Si el valor CSV es igual al de la BD, no debe generar diff."""
    conn = _FakeConn([
        {"id": 3, "serie": "SN-EXISTENTE", "valor_reposicion": None, "bh_url": None, "fecha_compra": None}
    ])
    raw = _make_csv({"id": "3", "serie": "SN-EXISTENTE"})
    result = import_inventario_csv(conn, raw, dry_run=True)
    assert result["actualizados"] == 0
    assert result["sin_cambio"] >= 1
    assert result["diff"] == []


def test_import_no_encontrado():
    """IDs no existentes en la BD deben aparecer en no_encontrados."""
    conn = _FakeConn([])
    raw = _make_csv({"id": "999", "serie": "SN-X"})
    result = import_inventario_csv(conn, raw, dry_run=True)
    assert 999 in result["no_encontrados"]
    assert result["actualizados"] == 0


def test_import_valor_reposicion_invalido():
    """Un valor_reposicion no numérico debe ir a errores sin cancelar el lote."""
    conn = _FakeConn([
        {"id": 1, "serie": None, "valor_reposicion": None, "bh_url": None, "fecha_compra": None},
        {"id": 2, "serie": None, "valor_reposicion": None, "bh_url": None, "fecha_compra": None},
    ])
    raw = _make_csv(
        {"id": "1", "valor_reposicion": "no-es-numero"},
        {"id": "2", "serie": "SN-OK"},
    )
    result = import_inventario_csv(conn, raw, dry_run=True)
    assert len(result["errores"]) == 1
    # La segunda fila sí se procesa
    assert result["actualizados"] == 1


def test_import_fecha_compra_iso_y_ddmm():
    """Acepta YYYY-MM-DD y DD/MM/YYYY."""
    conn = _FakeConn([
        {"id": 1, "serie": None, "valor_reposicion": None, "bh_url": None, "fecha_compra": None},
        {"id": 2, "serie": None, "valor_reposicion": None, "bh_url": None, "fecha_compra": None},
    ])
    raw = _make_csv(
        {"id": "1", "fecha_compra": "2024-03-15"},
        {"id": "2", "fecha_compra": "15/03/2024"},
    )
    result = import_inventario_csv(conn, raw, dry_run=True)
    assert result["actualizados"] == 2
    fechas = {d["id"]: d["despues"] for d in result["diff"]}
    assert fechas[1] == "2024-03-15"
    assert fechas[2] == "2024-03-15"


def test_import_csv_sin_id_column():
    """CSV sin columna 'id' debe levantar CSVImportError."""
    conn = _FakeConn([])
    raw = _make_csv({"nombre": "Sony FX3", "serie": "SN-001"})
    with pytest.raises(CSVImportError, match="id"):
        import_inventario_csv(conn, raw, dry_run=True)


def test_import_bom_utf8():
    """CSV con BOM debe parsearse sin error."""
    conn = _FakeConn([
        {"id": 5, "serie": None, "valor_reposicion": None, "bh_url": None, "fecha_compra": None}
    ])
    # BOM explícito al inicio
    raw = "﻿id,serie\r\n5,SN-BOM\r\n".encode("utf-8")
    result = import_inventario_csv(conn, raw, dry_run=True)
    assert result["actualizados"] == 1


def test_import_columnas_extra_ignoradas():
    """Columnas extra (nombre, marca, specs) no deben causar error."""
    conn = _FakeConn([
        {"id": 7, "serie": None, "valor_reposicion": None, "bh_url": None, "fecha_compra": None}
    ])
    raw = _make_csv({"id": "7", "nombre": "Sony FX3", "marca": "Sony",
                     "serie": "SN-007", "specs": "Sensor: Full-frame"})
    result = import_inventario_csv(conn, raw, dry_run=True)
    assert result["actualizados"] == 1
    assert result["diff"][0]["campo"] == "serie"


def test_inventario_csv_exporter_columns():
    """export_inventario_csv debe tener las columnas correctas."""
    import csv as _csv, io as _io
    from dataio.csv_exporters import export_inventario_csv

    class _FC:
        def fetchall(self):
            return []
    class _FConn:
        def execute(self, sql, p=None):
            return _FC()

    out = export_inventario_csv(_FConn())
    reader = _csv.reader(_io.StringIO(out[1:]))  # skip BOM
    header = next(reader)
    assert header == ["id", "nombre", "marca", "serie", "valor_reposicion", "bh_url", "fecha_compra"]


def test_equipos_csv_exporter_includes_valor_bh():
    """export_equipos_csv debe incluir valor_reposicion y bh_url (#1051)."""
    import csv as _csv, io as _io
    from dataio.csv_exporters import export_equipos_csv

    class _FC:
        def fetchall(self):
            return []
    class _FConn:
        def execute(self, sql, p=None):
            return _FC()

    out = export_equipos_csv(_FConn())
    reader = _csv.reader(_io.StringIO(out[1:]))  # skip BOM
    header = next(reader)
    assert "valor_reposicion" in header, "export_equipos_csv debe incluir valor_reposicion"
    assert "bh_url" in header, "export_equipos_csv debe incluir bh_url"
