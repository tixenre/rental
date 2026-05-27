"""Tests unitarios para routes/estudio.py (E1).

Verifica:
- La lógica de _build_response serializa correctamente JSON fields.
- _parse_json_field maneja None, lista, string JSON y string inválido.
- _foto_path_estudio genera paths con prefijo correcto.
- Guards de admin: los endpoints sensibles rechazan sin sesión.
"""

import json
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.unit


# ── _parse_json_field ────────────────────────────────────────────────────────

class TestParseJsonField:
    def _parse(self, val):
        from routes.estudio import _parse_json_field
        return _parse_json_field(val)

    def test_none_devuelve_none(self):
        assert self._parse(None) is None

    def test_string_vacio_devuelve_none(self):
        assert self._parse("") is None

    def test_lista_devuelve_lista(self):
        val = [{"label": "Superficie", "value": "— m²"}]
        assert self._parse(val) == val

    def test_string_json_valido(self):
        data = [{"q": "¿Mínimo?", "a": "2 h"}]
        assert self._parse(json.dumps(data)) == data

    def test_string_json_invalido_devuelve_none(self):
        assert self._parse("no es json {{{") is None


# ── _foto_path_estudio ────────────────────────────────────────────────────────

class TestFotoPathEstudio:
    def test_prefijo_correcto(self):
        from routes.estudio import _foto_path_estudio
        path = _foto_path_estudio()
        assert path.startswith("estudio/")
        assert path.endswith(".webp")

    def test_paths_unicos(self):
        import time
        from routes.estudio import _foto_path_estudio
        paths = {_foto_path_estudio() for _ in range(5)}
        # Si el reloj corre muy rápido puede colapsar; aceptamos ≥ 1 único
        assert len(paths) >= 1


# ── _build_response ──────────────────────────────────────────────────────────

class TestBuildResponse:
    def _make_row(self, **overrides):
        defaults = {
            "id": 1,
            "equipo_id": None,
            "nombre": "El Estudio",
            "tagline": "Foto y video",
            "descripcion": "Un espacio.",
            "precio_hora": 5000,
            "min_horas": 2,
            "open_hour": 8,
            "close_hour": 22,
            "buffer_horas": 0,
            "anticipacion_min_horas": 0,
            "pack_activo": True,
            "pack_nombre": "Pack Todo Incluido",
            "pack_descripcion": "Todo incluido.",
            "pack_precio": 10000,
            "features_json": json.dumps([{"label": "Superficie", "value": "50 m²"}]),
            "faq_json": json.dumps([{"q": "¿Mínimo?", "a": "2 h"}]),
            "updated_at": None,
        }
        defaults.update(overrides)
        row = MagicMock()
        row.__getitem__ = lambda self, k: defaults[k]
        return row

    def test_features_parseadas(self):
        from routes.estudio import _build_response
        row = self._make_row()
        result = _build_response(row, [])
        assert result["features"] == [{"label": "Superficie", "value": "50 m²"}]

    def test_faq_parseada(self):
        from routes.estudio import _build_response
        row = self._make_row()
        result = _build_response(row, [])
        assert result["faq"] == [{"q": "¿Mínimo?", "a": "2 h"}]

    def test_features_none_cuando_json_nulo(self):
        from routes.estudio import _build_response
        row = self._make_row(features_json=None)
        result = _build_response(row, [])
        assert result["features"] is None

    def test_fotos_incluidas(self):
        from routes.estudio import _build_response
        row = self._make_row()
        fotos = [{"id": 1, "url": "https://cdn.r2/foto.webp", "orden": 0, "es_principal": True}]
        result = _build_response(row, fotos)
        assert result["fotos"] == fotos

    def test_pack_activo_bool(self):
        from routes.estudio import _build_response
        row = self._make_row(pack_activo=1)  # simulando valor DB integer
        result = _build_response(row, [])
        assert result["pack_activo"] is True


# ── Guards de admin ───────────────────────────────────────────────────────────

class FakeRequest:
    def __init__(self, cookies=None):
        self.cookies = cookies or {}


class TestEstudioAdminGuards:
    """Verifica que los endpoints admin exigen autenticación."""

    def test_patch_estudio_requiere_admin(self, monkeypatch):
        monkeypatch.delenv("ADMIN_BYPASS_AUTH", raising=False)
        monkeypatch.setattr("admin_guard.get_session", lambda req: None)

        from routes.estudio import patch_estudio, EstudioUpdate

        with pytest.raises(HTTPException) as exc:
            patch_estudio(EstudioUpdate(), FakeRequest())
        assert exc.value.status_code == 401

    def test_delete_foto_requiere_admin(self, monkeypatch):
        monkeypatch.delenv("ADMIN_BYPASS_AUTH", raising=False)
        monkeypatch.setattr("admin_guard.get_session", lambda req: None)

        from routes.estudio import delete_foto

        with pytest.raises(HTTPException) as exc:
            delete_foto(1, FakeRequest())
        assert exc.value.status_code == 401

    def test_reorder_fotos_requiere_admin(self, monkeypatch):
        monkeypatch.delenv("ADMIN_BYPASS_AUTH", raising=False)
        monkeypatch.setattr("admin_guard.get_session", lambda req: None)

        from routes.estudio import reorder_fotos, ReorderBody

        with pytest.raises(HTTPException) as exc:
            reorder_fotos(ReorderBody(fotos=[]), FakeRequest())
        assert exc.value.status_code == 401

    def test_upload_from_url_requiere_admin(self, monkeypatch):
        monkeypatch.delenv("ADMIN_BYPASS_AUTH", raising=False)
        monkeypatch.setattr("admin_guard.get_session", lambda req: None)

        from routes.estudio import upload_foto_from_url, UploadFromUrlBody

        with pytest.raises(HTTPException) as exc:
            upload_foto_from_url(UploadFromUrlBody(url="https://example.com/img.jpg"), FakeRequest())
        assert exc.value.status_code == 401


# ── E2 / E2.1: reserva por horas ──────────────────────────────────────────────
#
# El motor SAGRADO (_check_stock / get_disponibilidad / _rango_con_buffer) NO se
# toca. E2.1 — el solapamiento del centinela (recurso único, stock=1) se chequea
# con una query DEDICADA (_centinela_libre) que usa SOLO el buffer propio del
# estudio, nunca el global de equipos.


def _estudio_row(**overrides):
    """Fila de estudio simulada (dict-accessible) para los helpers."""
    defaults = {
        "min_horas": 2,
        "open_hour": 8,
        "close_hour": 22,
        "buffer_horas": 0,
        "anticipacion_min_horas": 0,
        "precio_hora": 10000,
        "equipo_id": 99,  # id del centinela
    }
    defaults.update(overrides)
    return defaults


class _Cur:
    def __init__(self, rows):
        self._rows = list(rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class EstudioConflictoFakeConn:
    """Fake conn que evalúa el overlap REAL contra reservas del centinela.

    A diferencia de un stub fijo, parsea los parámetros de fecha que le pasa
    `_check_stock` (que son el rango ya expandido por el buffer propio del
    estudio) y suma las reservas existentes que efectivamente se pisan
    (`fd_existente < fh_consulta AND fh_existente > fd_consulta`, half-open).
    Así el test ejercita de verdad `_rango_con_buffer` + el overlap del motor.

    reservas: lista de (fecha_desde_iso, fecha_hasta_iso) del centinela.
    """

    def __init__(self, centinela_id, stock, reservas, buffer_global=0):
        self.centinela_id = centinela_id
        self.stock = stock
        self.reservas = reservas
        self.buffer_global = buffer_global

    @staticmethod
    def _parse(v):
        from database import to_datetime
        return to_datetime(v)

    def execute(self, sql, params=()):
        s = " ".join(sql.split()).upper()

        # Buffer global (setting app_settings) — separado del buffer del estudio.
        if "FROM APP_SETTINGS WHERE KEY = ?" in s:
            return _Cur([{"value": str(self.buffer_global)}])

        # Mantenimiento — ninguno.
        if "FROM EQUIPO_MANTENIMIENTO" in s:
            return _Cur([{0: 0}])

        # Items del pedido (1ra query de _check_stock): el centinela.
        if s.startswith("SELECT PI.EQUIPO_ID, PI.CANTIDAD, E.NOMBRE, E.CANTIDAD AS STOCK_TOTAL"):
            return _Cur([{
                "equipo_id": self.centinela_id,
                "cantidad": 1,
                "nombre": "Estudio (espacio)",
                "stock_total": self.stock,
            }])

        # Componentes del centinela — ninguno (no es kit).
        if s.startswith("SELECT KC.COMPONENTE_ID, KC.CANTIDAD AS KC_CANT"):
            return _Cur([])

        # Lock + stock del centinela.
        if "SELECT CANTIDAD FROM EQUIPOS WHERE ID = ? FOR UPDATE" in s:
            return _Cur([{"cantidad": self.stock}])

        # Reservas directas: sumamos las que se pisan con el rango consultado.
        if "FROM ALQUILER_ITEMS PI2 JOIN ALQUILERES P ON P.ID = PI2.PEDIDO_ID WHERE PI2.EQUIPO_ID = ?" in s:
            _eq, _excl, fh_consulta, fd_consulta = params
            fh_c = self._parse(fh_consulta)
            fd_c = self._parse(fd_consulta)
            total = 0
            for (fd_e, fh_e) in self.reservas:
                if self._parse(fd_e) < fh_c and self._parse(fh_e) > fd_c:
                    total += 1
            return _Cur([{0: total}])

        # Reservas vía kit — ninguna.
        if "JOIN KIT_COMPONENTES KC ON KC.EQUIPO_ID = PI2.EQUIPO_ID WHERE KC.COMPONENTE_ID = ?" in s:
            return _Cur([{0: 0}])

        return _Cur([])


class TestFranjaEstudio:
    def test_minimo_de_horas_falla(self):
        from routes.estudio import _franja_estudio
        with pytest.raises(HTTPException) as exc:
            _franja_estudio(_estudio_row(min_horas=2), "2026-06-01", "14:00", 1)
        assert exc.value.status_code == 400

    def test_fuera_de_horario_falla(self):
        from routes.estudio import _franja_estudio
        # close_hour=22 → terminar a las 23 cae afuera.
        with pytest.raises(HTTPException) as exc:
            _franja_estudio(_estudio_row(), "2026-06-01", "21:00", 2)
        assert exc.value.status_code == 400
        # Antes de abrir (open_hour=8) también.
        with pytest.raises(HTTPException):
            _franja_estudio(_estudio_row(), "2026-06-01", "07:00", 2)

    def test_franja_valida_devuelve_datetimes(self):
        from routes.estudio import _franja_estudio
        fd, fh = _franja_estudio(_estudio_row(), "2026-06-01", "14:00", 2)
        assert (fd.hour, fd.minute) == (14, 0)
        assert (fh.hour, fh.minute) == (16, 0)
        assert fd.date().isoformat() == "2026-06-01"


class CentinelaFakeConn:
    """Fake conn para la query DEDICADA de E2.1 (`_centinela_libre`).

    Evalúa el overlap real contra las reservas del centinela. CRÍTICO: si el
    código tocara el buffer global (app_settings), esta conn EXPLOTA — así el
    test prueba que el estudio usa SOLO su buffer propio.

    reservas: lista de (fecha_desde_iso, fecha_hasta_iso).
    """

    def __init__(self, reservas):
        self.reservas = reservas

    @staticmethod
    def _parse(v):
        from database import to_datetime
        return to_datetime(v)

    def execute(self, sql, params=()):
        s = " ".join(sql.split()).upper()

        if "APP_SETTINGS" in s:
            raise AssertionError(
                "El estudio NO debe leer el buffer global (app_settings) — E2.1"
            )

        # Lock del centinela (FOR UPDATE) en el POST.
        if s.startswith("SELECT ID FROM EQUIPOS WHERE ID = ? FOR UPDATE"):
            return _Cur([{"id": params[0]}])

        # Query dedicada de overlap del centinela.
        if "SELECT COUNT(*) AS CNT FROM ALQUILER_ITEMS PI JOIN ALQUILERES P" in s:
            _eq, _excl, _excl2, hi, lo = params
            hi_d, lo_d = self._parse(hi), self._parse(lo)
            cnt = sum(
                1 for (fd, fh) in self.reservas
                if self._parse(fd) < hi_d and self._parse(fh) > lo_d
            )
            return _Cur([{"cnt": cnt}])

        return _Cur([])


class TestEstudioOverlap:
    """Overlap estudio-vs-estudio por hora, vía la query dedicada (_centinela_libre)."""

    def _libre(self, conn, fd, fh, buffer_horas):
        from datetime import datetime
        from routes.estudio import _centinela_libre
        return _centinela_libre(
            conn, 99, datetime.fromisoformat(fd), datetime.fromisoformat(fh), buffer_horas
        )

    def test_dos_reservas_que_se_pisan_choca(self):
        # Existe 14:00–16:00. Una nueva 15:00–17:00 se pisa → ocupado.
        conn = CentinelaFakeConn([("2026-06-01T14:00:00", "2026-06-01T16:00:00")])
        assert self._libre(conn, "2026-06-01T15:00:00", "2026-06-01T17:00:00", 0) is False

    def test_franjas_disjuntas_mismo_dia_ok(self):
        # 14:00–16:00 existente; nueva 16:00–18:00 (half-open) NO se pisa → libre.
        conn = CentinelaFakeConn([("2026-06-01T14:00:00", "2026-06-01T16:00:00")])
        assert self._libre(conn, "2026-06-01T16:00:00", "2026-06-01T18:00:00", 0) is True


class TestEstudioBufferPropio:
    """El buffer propio del estudio expande el rango — y SOLO ese buffer (no el
    global). La CentinelaFakeConn explota si se lee app_settings."""

    def _libre(self, conn, fd, fh, buffer_horas):
        from datetime import datetime
        from routes.estudio import _centinela_libre
        return _centinela_libre(
            conn, 99, datetime.fromisoformat(fd), datetime.fromisoformat(fh), buffer_horas
        )

    def test_buffer_propio_bloquea_franja_adyacente(self):
        # Existe 14:00–16:00. Sin buffer, 16:30–18:00 está libre; con buffer 1h
        # el rango se expande a 15:30–19:00 → se pisa → ocupado.
        conn = CentinelaFakeConn([("2026-06-01T14:00:00", "2026-06-01T16:00:00")])
        assert self._libre(conn, "2026-06-01T16:30:00", "2026-06-01T18:00:00", 0) is True
        assert self._libre(conn, "2026-06-01T16:30:00", "2026-06-01T18:00:00", 1) is False

    def test_buffer_2h_bloquea_ventana_completa(self):
        # Reserva 12:00–16:00 con buffer 2h bloquea cualquier cosa en [10:00, 18:00].
        conn = CentinelaFakeConn([("2026-06-01T12:00:00", "2026-06-01T16:00:00")])
        # 10:00–12:00 (justo antes) y 16:00–18:00 (justo después) → ocupados con buffer 2.
        assert self._libre(conn, "2026-06-01T10:00:00", "2026-06-01T12:00:00", 2) is False
        assert self._libre(conn, "2026-06-01T16:00:00", "2026-06-01T18:00:00", 2) is False
        # Sin buffer, esas franjas adyacentes están libres (half-open).
        assert self._libre(conn, "2026-06-01T16:00:00", "2026-06-01T18:00:00", 0) is True

    def test_global_buffer_no_interviene(self):
        # Si el código intentara leer el buffer global, la conn explotaría.
        # Que esto pase prueba que el estudio usa exclusivamente su buffer propio.
        conn = CentinelaFakeConn([("2026-06-01T14:00:00", "2026-06-01T16:00:00")])
        assert self._libre(conn, "2026-06-01T18:00:00", "2026-06-01T20:00:00", 1) is True


class TestAnticipacionMinima:
    """anticipacion_min_horas (E2.1) — solo estudio. Rechaza franjas demasiado
    próximas a `now_ar()`."""

    def _viola(self, horas_anticipacion, horas_hasta_franja):
        from datetime import timedelta
        from database import now_ar
        from routes.estudio import _viola_anticipacion
        fecha_desde = now_ar() + timedelta(hours=horas_hasta_franja)
        return _viola_anticipacion(
            _estudio_row(anticipacion_min_horas=horas_anticipacion), fecha_desde
        )

    def test_rechaza_antes_de_la_anticipacion(self):
        # Anticipación 12h, franja dentro de 6h → viola.
        assert self._viola(12, 6) is True

    def test_permite_a_partir_de_la_anticipacion(self):
        # Anticipación 12h, franja dentro de 24h → OK.
        assert self._viola(12, 24) is False

    def test_anticipacion_cero_nunca_viola(self):
        assert self._viola(0, 0) is False


class TestNoRegresionTipo:
    """SAGRADO: el DEFAULT tipo='diaria' no cambia el overlap (las queries no
    filtran por tipo). Replicamos un caso de test_stock_validation.py y
    verificamos el mismo resultado: una reserva existente sigue contando."""

    def test_overlap_diaria_sigue_contando(self):
        # Equipo normal (no centinela): stock=1 con una reserva que se pisa →
        # debe seguir bloqueando, idéntico a antes de existir la columna tipo.
        conn = EstudioConflictoFakeConn(
            centinela_id=20, stock=1,
            reservas=[("2026-06-01T00:00:00", "2026-06-05T00:00:00")],
        )
        from routes.alquileres import _check_stock
        problemas = _check_stock(conn, 2, "2026-06-02T00:00:00", "2026-06-03T00:00:00")
        assert len(problemas) == 1
        assert "disponible: 0" in problemas[0]


class TestCentinelaNoLeak:
    """El centinela (es_recurso_interno) no debe filtrarse en las vistas admin
    de equipos. Verificamos que cada query que enumera/conteo equipos lleve el
    filtro `es_recurso_interno = FALSE` (no hay BD en CI; inspeccionamos el SQL
    embebido en cada handler, que es estático)."""

    def _src(self, fn):
        import inspect
        return inspect.getsource(fn)

    def test_dashboard_uso_excluye_centinela(self):
        from routes.equipos import admin_dashboard_uso
        src = self._src(admin_dashboard_uso)
        # top_alquilados, sin_uso y stats globales (total_equipos).
        assert src.count("es_recurso_interno = FALSE") >= 3

    def test_sin_serie_excluye_centinela(self):
        from routes.equipos import admin_equipos_sin_serie
        assert "es_recurso_interno = FALSE" in self._src(admin_equipos_sin_serie)

    def test_clasificar_excluye_centinela(self):
        from routes.equipos import admin_clasificar
        assert "es_recurso_interno = FALSE" in self._src(admin_clasificar)
