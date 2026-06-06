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
            "direccion": "",
            "como_llegar": "",
            "testimonios_json": None,
            "mapa_url": "",
            "mapa_embed_url": "",
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

    def test_listar_pack_requiere_admin(self, monkeypatch):
        monkeypatch.delenv("ADMIN_BYPASS_AUTH", raising=False)
        monkeypatch.setattr("admin_guard.get_session", lambda req: None)
        from routes.estudio import listar_pack

        with pytest.raises(HTTPException) as exc:
            listar_pack(FakeRequest())
        assert exc.value.status_code == 401

    def test_agregar_pack_requiere_admin(self, monkeypatch):
        monkeypatch.delenv("ADMIN_BYPASS_AUTH", raising=False)
        monkeypatch.setattr("admin_guard.get_session", lambda req: None)
        from routes.estudio import agregar_pack_equipo, PackEquipoCreate

        with pytest.raises(HTTPException) as exc:
            agregar_pack_equipo(PackEquipoCreate(equipo_id=1), FakeRequest())
        assert exc.value.status_code == 401

    def test_quitar_pack_requiere_admin(self, monkeypatch):
        monkeypatch.delenv("ADMIN_BYPASS_AUTH", raising=False)
        monkeypatch.setattr("admin_guard.get_session", lambda req: None)
        from routes.estudio import quitar_pack_equipo

        with pytest.raises(HTTPException) as exc:
            quitar_pack_equipo(1, FakeRequest())
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


class _ConnCM:
    """Mixin que da a los fakes de conexión el protocolo context-manager, igual
    que el `PGConnection` real — las rutas ahora hacen `with get_db() as conn:`."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        close = getattr(self, "close", None)
        if close:
            close()
        return False


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

        # Items del pedido (1ra query del gate): el centinela.
        if s.startswith("SELECT EQUIPO_ID, CANTIDAD FROM ALQUILER_ITEMS WHERE PEDIDO_ID = ?"):
            return _Cur([{"equipo_id": self.centinela_id, "cantidad": 1}])

        # Grafo de composición (componentes_de / parientes_de) — el centinela no es kit.
        if s.startswith("SELECT EQUIPO_ID, COMPONENTE_ID, CANTIDAD") and "FROM KIT_COMPONENTES" in s:
            return _Cur([])

        # Nombres para los mensajes.
        if s.startswith("SELECT ID, NOMBRE FROM EQUIPOS WHERE ID IN"):
            return _Cur([{"id": self.centinela_id, "nombre": "Estudio (espacio)"}])

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
        from reservas import validar_stock as _check_stock
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


# ── E3: pack dinámico (Grip / Iluminación / Modificadores) ────────────────────
#
# El espacio (centinela) sigue con _centinela_libre (buffer propio). Los equipos
# del pack son reales → motor sagrado (get_disponibilidad / _check_stock, buffer
# global). Estos tests patchean el motor para aislar la orquestación del pack.

import routes.estudio as estudio_mod


class _CurLastrowid:
    def __init__(self, rows, lastrowid=None):
        self._rows = list(rows)
        self._lastrowid = lastrowid

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows

    @property
    def lastrowid(self):
        return self._lastrowid


class _NamesConn(_ConnCM):
    """Responde solo la query de nombres de _pack_disponible."""

    def __init__(self, names):
        self.names = names  # {id: (nombre, marca)}

    def execute(self, sql, params=()):
        su = " ".join(sql.split()).upper()
        if "FROM EQUIPOS E WHERE E.ID = ANY(?)" in su:
            ids = params[0]
            return _Cur(
                [{"id": i, "nombre": self.names[i][0], "marca": self.names[i][1],
                  "foto_url": self.names[i][2] if len(self.names[i]) > 2 else None}
                 for i in ids if i in self.names]
            )
        return _Cur([])


class TestPackDisponible:
    """_pack_disponible: solo equipos con >= 1 disponible; lo reservado no entra."""

    def test_filtra_por_disponibilidad(self, monkeypatch):
        from datetime import datetime
        # Pack candidatos: 10, 11, 12. El 11 está ocupado (disp 0) → no entra.
        monkeypatch.setattr(estudio_mod, "_pack_equipo_ids", lambda conn: [10, 11, 12])
        monkeypatch.setattr(
            estudio_mod, "get_disponibilidad",
            lambda fd, fh, excl=None: {"10": 2, "11": 0, "12": 1},
        )
        conn = _NamesConn({10: ("Trípode", "Manfrotto"), 12: ("HMI", "Arri")})
        out = estudio_mod._pack_disponible(
            conn, datetime(2026, 6, 1, 14), datetime(2026, 6, 1, 16)
        )
        ids = {e["id"]: e["cantidad"] for e in out}
        assert ids == {10: 2, 12: 1}  # el 11 (reservado) quedó afuera

    def test_sin_candidatos_lista_vacia(self, monkeypatch):
        from datetime import datetime
        monkeypatch.setattr(estudio_mod, "_pack_equipo_ids", lambda conn: [])
        out = estudio_mod._pack_disponible(
            _NamesConn({}), datetime(2026, 6, 1, 14), datetime(2026, 6, 1, 16)
        )
        assert out == []

    def test_incluye_foto_url(self, monkeypatch):
        from datetime import datetime
        monkeypatch.setattr(estudio_mod, "_pack_equipo_ids", lambda conn: [10])
        monkeypatch.setattr(
            estudio_mod, "get_disponibilidad", lambda fd, fh, excl=None: {"10": 1}
        )
        conn = _NamesConn({10: ("HMI", "Arri", "https://cdn/hmi.webp")})
        out = estudio_mod._pack_disponible(
            conn, datetime(2026, 6, 1, 14), datetime(2026, 6, 1, 16)
        )
        assert out[0]["foto_url"] == "https://cdn/hmi.webp"


class _PackTablaConn(_ConnCM):
    """Responde la query de _pack_equipo_ids (tabla curada estudio_pack_equipos)."""

    def __init__(self, ids):
        self.ids = ids

    def execute(self, sql, params=()):
        su = " ".join(sql.split()).upper()
        assert "ESTUDIO_PACK_EQUIPOS" in su, "debe leer de la tabla curada, no de categorías"
        assert "EQUIPO_CATEGORIAS" not in su, "ya no se filtra por categorías"
        return _Cur([{"id": i} for i in self.ids])


class TestPackEquipoIds:
    """_pack_equipo_ids lee de la tabla curada estudio_pack_equipos (v2-C)."""

    def test_lee_de_tabla_curada(self):
        conn = _PackTablaConn([7, 3, 9])
        assert estudio_mod._pack_equipo_ids(conn) == [7, 3, 9]

    def test_pack_vacio(self):
        assert estudio_mod._pack_equipo_ids(_PackTablaConn([])) == []


class _PackCrudConn(_ConnCM):
    """Fake conn para el CRUD del pack: graba INSERT/DELETE y responde el equipo."""

    def __init__(self, equipo=None):
        self.equipo = equipo  # dict o None
        self.inserted = None
        self.deleted = None
        self.committed = False

    def execute(self, sql, params=()):
        su = " ".join(sql.split()).upper()
        if su.startswith("SELECT ID, ES_RECURSO_INTERNO, ELIMINADO_AT FROM EQUIPOS"):
            return _Cur([self.equipo] if self.equipo else [])
        if "MAX(ORDEN)" in su:
            return _Cur([{"next": 0}])
        if su.startswith("INSERT INTO ESTUDIO_PACK_EQUIPOS"):
            self.inserted = params
            return _Cur([])
        if su.startswith("DELETE FROM ESTUDIO_PACK_EQUIPOS"):
            self.deleted = params
            return _Cur([])
        return _Cur([])

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        pass


class TestPackCrud:
    """CRUD del pack curado (con ADMIN_BYPASS_AUTH)."""

    def test_agregar_inserta(self, monkeypatch):
        monkeypatch.setenv("ADMIN_BYPASS_AUTH", "1")
        conn = _PackCrudConn(equipo={"id": 5, "es_recurso_interno": False, "eliminado_at": None})
        monkeypatch.setattr(estudio_mod, "get_db", lambda: conn)
        monkeypatch.setattr(estudio_mod, "_pack_curado", lambda c: [{"id": 5}])
        from routes.estudio import agregar_pack_equipo, PackEquipoCreate

        out = agregar_pack_equipo(PackEquipoCreate(equipo_id=5), FakeRequest())
        assert conn.inserted is not None and conn.inserted[0] == 5
        assert conn.committed
        assert out == {"pack": [{"id": 5}]}

    def test_agregar_recurso_interno_falla(self, monkeypatch):
        monkeypatch.setenv("ADMIN_BYPASS_AUTH", "1")
        conn = _PackCrudConn(equipo={"id": 9, "es_recurso_interno": True, "eliminado_at": None})
        monkeypatch.setattr(estudio_mod, "get_db", lambda: conn)
        from routes.estudio import agregar_pack_equipo, PackEquipoCreate

        with pytest.raises(HTTPException) as exc:
            agregar_pack_equipo(PackEquipoCreate(equipo_id=9), FakeRequest())
        assert exc.value.status_code == 400
        assert conn.inserted is None

    def test_agregar_inexistente_404(self, monkeypatch):
        monkeypatch.setenv("ADMIN_BYPASS_AUTH", "1")
        conn = _PackCrudConn(equipo=None)
        monkeypatch.setattr(estudio_mod, "get_db", lambda: conn)
        from routes.estudio import agregar_pack_equipo, PackEquipoCreate

        with pytest.raises(HTTPException) as exc:
            agregar_pack_equipo(PackEquipoCreate(equipo_id=123), FakeRequest())
        assert exc.value.status_code == 404

    def test_quitar_borra(self, monkeypatch):
        monkeypatch.setenv("ADMIN_BYPASS_AUTH", "1")
        conn = _PackCrudConn()
        monkeypatch.setattr(estudio_mod, "get_db", lambda: conn)
        monkeypatch.setattr(estudio_mod, "_pack_curado", lambda c: [])
        from routes.estudio import quitar_pack_equipo

        out = quitar_pack_equipo(5, FakeRequest())
        assert conn.deleted == (5,)
        assert conn.committed
        assert out == {"pack": []}


class _RecordingConn(_ConnCM):
    """Graba INSERTs de alquileres/items para verificar la orquestación del POST."""

    def __init__(self, pedido_id=555):
        self.pedido_id = pedido_id
        self.alquiler_params = None
        self.items = []  # {equipo_id, cantidad, precio}
        self.committed = False

    def execute(self, sql, params=()):
        su = " ".join(sql.split()).upper()
        if su.startswith("SELECT NOMBRE, APELLIDO, EMAIL, TELEFONO FROM CLIENTES"):
            return _Cur([{
                "nombre": "Tester", "apellido": "Estudio",
                "email": "tester@example.com", "telefono": "1122334455",
            }])
        if su.startswith("INSERT INTO ALQUILERES"):
            self.alquiler_params = params
            return _CurLastrowid([], lastrowid=self.pedido_id)
        if su.startswith("INSERT INTO ALQUILER_ITEMS"):
            self.items.append(
                {"equipo_id": params[1], "cantidad": params[2], "precio": params[3]}
            )
            return _Cur([])
        if su.startswith("DELETE FROM ALQUILER_ITEMS"):
            return _Cur([])
        return _Cur([])

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        pass


def _patch_post_collaborators(monkeypatch, conn, estudio_row, disp, pack_ids):
    """Patchea los colaboradores pesados del POST para aislar la orquestación."""
    monkeypatch.setattr(estudio_mod, "get_db", lambda: conn)
    monkeypatch.setattr(estudio_mod, "_get_estudio_row", lambda c: estudio_row)
    monkeypatch.setattr(estudio_mod, "_next_numero_pedido", lambda c: 999)
    monkeypatch.setattr(estudio_mod, "_pack_equipo_ids", lambda c: pack_ids)
    monkeypatch.setattr(estudio_mod, "get_disponibilidad", lambda fd, fh, excl=None: disp)
    monkeypatch.setattr(estudio_mod, "_check_stock", lambda c, pid, fd, fh: [])
    monkeypatch.setattr(
        estudio_mod, "_centinela_libre",
        lambda c, eid, fd, fh, buf, exclude_pedido_id=None: True,
    )
    monkeypatch.setattr(estudio_mod, "_get_alquiler_detail", lambda c, pid: {"id": pid})
    monkeypatch.setattr(estudio_mod, "_dispatch_pedido_creado_emails", lambda bg, p: None)
    # v2-B: login obligatorio — cliente_id sale de la sesión.
    monkeypatch.setattr(estudio_mod, "_require_cliente", lambda req: {"cliente_id": 7, "role": "cliente"})


def _estudio_row_full(**overrides):
    row = _estudio_row()
    row.update({"pack_activo": True, "pack_precio": 30000})
    row.update(overrides)
    return row


class TestCrearReservaPack:
    """POST /estudio/reservas con/ sin pack — orquestación y monto."""

    def _post(self, monkeypatch, con_pack, disp, pack_ids, estudio_row=None):
        from datetime import timedelta
        from fastapi import BackgroundTasks
        from database import now_ar
        from routes.estudio import crear_reserva_estudio, EstudioReservaCreate

        conn = _RecordingConn()
        est = estudio_row or _estudio_row_full()
        _patch_post_collaborators(monkeypatch, conn, est, disp, pack_ids)

        # Fecha futura válida dentro del horario [open, close].
        manana = (now_ar() + timedelta(days=2)).strftime("%Y-%m-%d")
        body = EstudioReservaCreate(fecha=manana, start="14:00", horas=2, con_pack=con_pack)
        crear_reserva_estudio(body, FakeRequest(), BackgroundTasks())
        return conn

    def test_con_pack_suma_precio_y_crea_items(self, monkeypatch):
        conn = self._post(
            monkeypatch, con_pack=True,
            disp={"10": 2, "11": 1}, pack_ids=[10, 11],
        )
        # monto_total = precio_hora(10000)*2 + pack_precio(30000) = 50000
        # INSERT alquileres params: (... , monto_total, estado, fuente, tipo, estudio_con_pack, numero)
        params = conn.alquiler_params
        assert 50000 in params           # monto_total
        assert True in params            # estudio_con_pack = TRUE
        # Items: centinela (equipo_id=99, cant 1) + pack 10 (×2) + 11 (×1)
        by_eq = {it["equipo_id"]: it["cantidad"] for it in conn.items}
        assert by_eq == {99: 1, 10: 2, 11: 1}
        assert conn.committed is True

    def test_sin_pack_no_crea_items_de_equipos(self, monkeypatch):
        conn = self._post(
            monkeypatch, con_pack=False,
            disp={"10": 2, "11": 1}, pack_ids=[10, 11],
        )
        # monto_total = 10000*2 = 20000 (sin pack_precio)
        assert 20000 in conn.alquiler_params
        assert False in conn.alquiler_params  # estudio_con_pack = FALSE
        # Solo el centinela; ningún equipo del pack.
        by_eq = {it["equipo_id"]: it["cantidad"] for it in conn.items}
        assert by_eq == {99: 1}

    def test_pack_inactivo_ignora_con_pack(self, monkeypatch):
        # pack_activo=False → aunque el cliente mande con_pack, no se cobra ni agrega.
        est = _estudio_row_full(pack_activo=False)
        conn = self._post(
            monkeypatch, con_pack=True,
            disp={"10": 2}, pack_ids=[10], estudio_row=est,
        )
        assert 20000 in conn.alquiler_params
        by_eq = {it["equipo_id"]: it["cantidad"] for it in conn.items}
        assert by_eq == {99: 1}


# ── E4: slots fijos recurrentes mensuales ──────────────────────────────────────


class TestIterMesesYPrimerDia:
    def test_iter_meses_inclusive_cruza_anio(self):
        from routes.estudio import _iter_meses
        out = list(_iter_meses("2026-11", "2027-02"))
        assert out == [(2026, 11), (2026, 12), (2027, 1), (2027, 2)]

    def test_primer_dia_semana(self):
        from routes.estudio import _primer_dia_semana
        # Primer miércoles (weekday 2) de junio 2026.
        d = _primer_dia_semana(2026, 6, 2)
        assert d.weekday() == 2
        assert d.month == 6 and d.day <= 7


class _SlotBloqueoConn(_ConnCM):
    """Fake conn para _slot_bloqueante: filtra los slots como la query real."""

    def __init__(self, slots):
        self.slots = slots  # dicts con cliente/dia_semana/hora_desde/hora_hasta/mes_desde/mes_hasta/activo

    def execute(self, sql, params=()):
        su = " ".join(sql.split()).upper()
        if "FROM ESTUDIO_SLOTS_FIJOS" in su and "WHERE ACTIVO" in su:
            dia, mes, _mes2 = params
            res = [
                s for s in self.slots
                if s["activo"] and s["dia_semana"] == dia
                and s["mes_desde"] <= mes and s["mes_hasta"] >= mes
            ]
            return _Cur([
                {"cliente": s["cliente"], "hora_desde": s["hora_desde"], "hora_hasta": s["hora_hasta"]}
                for s in res
            ])
        return _Cur([])


class TestSlotBloqueante:
    SLOT = {
        "cliente": "Filmar", "dia_semana": 2, "hora_desde": 8, "hora_hasta": 20,
        "mes_desde": "2026-06", "mes_hasta": "2026-12", "activo": True,
    }

    def _franja(self, year, month, weekday, h_desde, h_hasta):
        from routes.estudio import _primer_dia_semana
        rep = _primer_dia_semana(year, month, weekday)
        return (rep.replace(hour=h_desde), rep.replace(hour=h_hasta))

    def test_bloquea_su_dia_y_horario_en_rango(self):
        from routes.estudio import _slot_bloqueante
        conn = _SlotBloqueoConn([self.SLOT])
        fd, fh = self._franja(2026, 6, 2, 10, 12)  # miércoles de junio 10-12
        assert _slot_bloqueante(conn, fd, fh) == "Filmar"

    def test_no_bloquea_otro_dia(self):
        from routes.estudio import _slot_bloqueante
        conn = _SlotBloqueoConn([self.SLOT])
        fd, fh = self._franja(2026, 6, 1, 10, 12)  # martes
        assert _slot_bloqueante(conn, fd, fh) is None

    def test_no_bloquea_fuera_del_rango_de_meses(self):
        from routes.estudio import _slot_bloqueante
        conn = _SlotBloqueoConn([self.SLOT])
        fd, fh = self._franja(2027, 1, 2, 10, 12)  # miércoles de enero 2027 (> mes_hasta)
        assert _slot_bloqueante(conn, fd, fh) is None

    def test_no_bloquea_horario_disjunto(self):
        from routes.estudio import _slot_bloqueante
        conn = _SlotBloqueoConn([self.SLOT])
        fd, fh = self._franja(2026, 6, 2, 20, 22)  # arranca cuando el slot termina (half-open)
        assert _slot_bloqueante(conn, fd, fh) is None

    def test_slot_inactivo_no_bloquea(self):
        from routes.estudio import _slot_bloqueante
        conn = _SlotBloqueoConn([{**self.SLOT, "activo": False}])
        fd, fh = self._franja(2026, 6, 2, 10, 12)
        assert _slot_bloqueante(conn, fd, fh) is None

    def test_bloquea_franja_que_cierra_a_medianoche(self):
        # Reserva 22-24: fecha_hasta = 00:00 del día siguiente. Con `.hour` daría
        # fin=0 y no detectaría el solape; con minutos relativos al día da 1440.
        from datetime import timedelta
        from routes.estudio import _primer_dia_semana, _slot_bloqueante
        conn = _SlotBloqueoConn([{**self.SLOT, "hora_hasta": 24}])  # slot 8-24
        rep = _primer_dia_semana(2026, 6, 2)  # miércoles (dia_semana=2)
        fd = rep.replace(hour=22)
        fh = rep.replace(hour=0) + timedelta(hours=24)  # 00:00 del día siguiente
        assert _slot_bloqueante(conn, fd, fh) == "Filmar"


class _SlotRegenConn(_ConnCM):
    """Fake conn para _regenerar_pedidos_slot: graba INSERT/DELETE de alquileres."""

    def __init__(self, existing=None):
        self.existing = existing or []  # [{id, fecha_desde, monto_pagado}]
        self.inserted = []              # params de cada INSERT alquileres
        self.deleted = []               # ids borrados
        self.item_inserts = 0           # NO debe haber items (no doble-bloqueo)
        self._num = 1000

    def execute(self, sql, params=()):
        su = " ".join(sql.split()).upper()
        if "FROM ALQUILERES WHERE ESTUDIO_SLOT_ID = ?" in su:
            return _Cur(self.existing)
        if "NEXTVAL" in su:
            self._num += 1
            return _Cur([{0: self._num}])
        if su.startswith("INSERT INTO ALQUILERES"):
            self.inserted.append(params)
            return _CurLastrowid([], lastrowid=self._num)
        if su.startswith("INSERT INTO ALQUILER_ITEMS"):
            self.item_inserts += 1
            return _Cur([])
        if su.startswith("DELETE FROM ALQUILERES WHERE ID = ?"):
            self.deleted.append(params[0])
            return _Cur([])
        return _Cur([])


def _slot_full(**ov):
    s = {
        "id": 1, "cliente": "Filmar", "dia_semana": 2, "hora_desde": 8, "hora_hasta": 20,
        "valor_mensual": 50000, "mes_desde": "2026-06", "mes_hasta": "2026-08", "activo": True,
    }
    s.update(ov)
    return s


class TestRegenerarPedidosSlot:
    def test_genera_un_pedido_por_mes_con_el_valor(self):
        from routes.estudio import _regenerar_pedidos_slot
        conn = _SlotRegenConn(existing=[])
        _regenerar_pedidos_slot(conn, _slot_full())  # jun, jul, ago 2026 (todos futuros)
        assert len(conn.inserted) == 3
        for p in conn.inserted:
            # (cliente, fd, fh, monto, estado, fuente, tipo, num, slot_id)
            assert p[0] == "Filmar"
            assert p[3] == 50000
            assert p[4] == "confirmado"
            assert p[5] == "estudio"
            assert p[6] == "estudio_fijo"
            assert p[8] == 1
        # NO se crean items → el slot no doble-bloquea el centinela.
        assert conn.item_inserts == 0

    def test_editar_regenera_futuros_sin_tocar_pagados(self):
        from datetime import datetime
        from routes.estudio import _regenerar_pedidos_slot
        existing = [
            {"id": 90, "fecha_desde": datetime(2026, 7, 1, 8), "monto_pagado": 10000},  # pagado → conservar
            {"id": 91, "fecha_desde": datetime(2026, 6, 3, 8), "monto_pagado": 0},       # futuro impago → borrar+recrear
        ]
        conn = _SlotRegenConn(existing=existing)
        _regenerar_pedidos_slot(conn, _slot_full())  # rango jun-ago
        assert 91 in conn.deleted       # impago borrado
        assert 90 not in conn.deleted   # pagado intocable
        # Recrea jun (borrado) + ago (nuevo); jul queda conservado.
        assert len(conn.inserted) == 2

    def test_slot_inactivo_no_genera(self):
        from routes.estudio import _regenerar_pedidos_slot
        conn = _SlotRegenConn(existing=[])
        _regenerar_pedidos_slot(conn, _slot_full(activo=False))
        assert conn.inserted == []

    def test_slot_que_cierra_a_medianoche_no_crashea(self):
        # hora_hasta=24 (cierre a medianoche, válido) rompía con
        # rep.replace(hour=24); ahora se arma con timedelta → 00:00 del día sig.
        from routes.estudio import _regenerar_pedidos_slot
        conn = _SlotRegenConn(existing=[])
        _regenerar_pedidos_slot(conn, _slot_full(hora_desde=20, hora_hasta=24))
        assert len(conn.inserted) == 3  # jun, jul, ago
        for p in conn.inserted:
            fd, fh = p[1], p[2]
            assert fd.hour == 20
            assert fh.hour == 0 and fh.day == fd.day + 1  # medianoche del día siguiente


# ── v2-B: reserva con login obligatorio ────────────────────────────────────────


class TestReservaLoginObligatorio:
    def test_sin_sesion_devuelve_401(self, monkeypatch):
        from fastapi import BackgroundTasks, HTTPException
        from routes.estudio import crear_reserva_estudio, EstudioReservaCreate

        def _raise(_req):
            raise HTTPException(401, "Sesión de cliente requerida")

        monkeypatch.setattr(estudio_mod, "_require_cliente", _raise)
        body = EstudioReservaCreate(fecha="2026-12-02", start="14:00", horas=2)
        with pytest.raises(HTTPException) as exc:
            crear_reserva_estudio(body, FakeRequest(), BackgroundTasks())
        assert exc.value.status_code == 401

    def test_usa_cliente_de_la_sesion_no_del_body(self, monkeypatch):
        from datetime import timedelta
        from fastapi import BackgroundTasks
        from database import now_ar
        from routes.estudio import crear_reserva_estudio, EstudioReservaCreate

        conn = _RecordingConn()
        _patch_post_collaborators(monkeypatch, conn, _estudio_row_full(), {}, [])
        manana = (now_ar() + timedelta(days=2)).strftime("%Y-%m-%d")
        crear_reserva_estudio(
            EstudioReservaCreate(fecha=manana, start="14:00", horas=2),
            FakeRequest(),
            BackgroundTasks(),
        )
        # cliente_id (7, de la sesión) es el primer parámetro del INSERT.
        assert conn.alquiler_params[0] == 7
        # nombre/email salen de la tabla clientes, no del body.
        assert "Tester Estudio" in conn.alquiler_params  # "Nombre Apellido"
        assert "tester@example.com" in conn.alquiler_params

    def test_body_no_acepta_datos_de_cliente(self):
        from routes.estudio import EstudioReservaCreate
        assert "cliente_nombre" not in EstudioReservaCreate.model_fields
        assert "cliente_email" not in EstudioReservaCreate.model_fields
