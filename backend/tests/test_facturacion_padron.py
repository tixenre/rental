"""Tests de services.facturacion.padron — resolver_persona() reintenta con
CADA emisor activo con cert hasta que uno devuelva la PersonaArca (cada
emisor delega su relación de ARCA de forma independiente); CUALQUIER otra
cosa (sin emisor disponible, AFIP caído, TODOS los emisores sin datos ni
motivo) levanta RuntimeError con el motivo real — nunca degrada a None en
silencio. Nunca rompe el FORMULARIO (el caller/route lo atrapa y sigue
siendo editable a mano), pero tampoco esconde la causa."""

from __future__ import annotations

from datetime import datetime

import pytest

from arca_fe.padron import WSAA_SERVICIO, PersonaArca
from services.facturacion.emisores_repo import EmisorArca
from services.facturacion.padron import resolver_persona, verificar_y_actualizar_receptor

pytestmark = pytest.mark.unit


def _emisor(nombre="pablo", activo=True, cert_cargado=True):
    return EmisorArca(
        id=1,
        nombre=nombre,
        cuit="20300000000",
        pto_vta=1,
        condicion_iva="responsable_inscripto",
        cert_cargado=cert_cargado,
        activo=activo,
        razon_social=None,
        domicilio=None,
        iibb=None,
        inicio_actividades=None,
        notas=None,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )


def test_sin_emisor_activo_con_cert_levanta_con_motivo(monkeypatch):
    """Regresión: esto devolvía None en silencio, indistinguible de "ARCA no
    tiene datos" — el admin nunca se enteraba de que la consulta ni siquiera
    se había podido intentar."""
    monkeypatch.setattr(
        "services.facturacion.emisores_repo.list_emisores",
        lambda conn: [_emisor(activo=False), _emisor(cert_cargado=False)],
    )
    with pytest.raises(RuntimeError, match="ningún emisor activo con certificado"):
        resolver_persona("20301234567", conn=object())


def test_afip_sin_datos_levanta_nombrando_el_emisor_y_el_ambiente(monkeypatch):
    """Caso real de prod: un CUIT que AFIP no devuelve. `get_persona` YA NO
    devuelve None — levanta ArcaResponseError/ArcaBusinessError con el motivo
    real. resolver_persona lo captura y arma un RuntimeError que nombra el
    emisor autenticador probado, su motivo, y EL AMBIENTE en que consultó
    (clave: homologación solo conoce CUIT de prueba, así que un 'sin datos' ahí
    es el ambiente, no un problema del CUIT)."""
    from arca_fe.errores import ArcaResponseError

    monkeypatch.setattr(
        "services.facturacion.emisores_repo.list_emisores",
        lambda conn: [_emisor(nombre="pablo")],
    )

    class _FakeCred:
        ambiente = "homologacion"
        cuit = 20300000000

    monkeypatch.setattr(
        "services.facturacion.config.credenciales", lambda emisor, conn: _FakeCred()
    )
    monkeypatch.setattr(
        "services.facturacion.wsaa_cache.get_ta",
        lambda emisor, conn, servicio=None: ("tok", "sign"),
    )
    monkeypatch.setattr(
        "arca_fe.padron.PadronClient.get_persona",
        lambda self, cuit: (_ for _ in ()).throw(
            ArcaResponseError("AFIP no devolvió datos de persona", raw="<XML-CRUDO>")
        ),
    )

    with pytest.raises(RuntimeError, match="pablo.*20300000000") as ei:
        resolver_persona("23373891029", conn=object())

    msg = str(ei.value)
    assert "AMBIENTE" in msg
    # el motivo real de AFIP + su respuesta cruda quedan en el mensaje
    assert "AFIP no devolvió datos de persona" in msg
    assert "<XML-CRUDO>" in msg


def test_usa_el_unico_emisor_activo_con_cert(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        "services.facturacion.emisores_repo.list_emisores",
        lambda conn: [_emisor(nombre="pablo")],
    )

    class _FakeCred:
        ambiente = "homologacion"
        cuit = 20300000000

    monkeypatch.setattr(
        "services.facturacion.config.credenciales",
        lambda emisor, conn: (captured.setdefault("emisor", emisor), _FakeCred())[1],
    )
    monkeypatch.setattr(
        "services.facturacion.wsaa_cache.get_ta",
        lambda emisor, conn, servicio=None: (
            captured.setdefault("servicio", servicio),
            ("tok", "sign"),
        )[1],
    )

    class _FakePersona:
        razon_social = "Empresa XYZ"

    monkeypatch.setattr(
        "arca_fe.padron.PadronClient.get_persona", lambda self, cuit: _FakePersona()
    )

    result = resolver_persona("30712345678", conn=object())

    assert result.razon_social == "Empresa XYZ"
    assert captured["emisor"] == "pablo"
    # Regresión: "ws_sr_padron_a5" es el id VIEJO — AFIP lo deprecó y renombró
    # el servicio a "ws_sr_constancia_inscripcion" (manual oficial
    # WS_SR_constancia_inscripcion v3.7); pedirle el TA a WSAA con el id viejo
    # hace que la relación no matchee y la consulta degrade silenciosamente a
    # "no se pudo autocompletar" — bug real de prod con un CUIT válido.
    assert captured["servicio"] == WSAA_SERVICIO == "ws_sr_constancia_inscripcion"


def test_reintenta_con_el_siguiente_emisor_si_el_primero_no_tiene_la_relacion(
    monkeypatch,
):
    """Caso real de prod: dos emisores activos con cert, cada uno delega su
    propia relación 'Consulta de constancia de inscripción' en ARCA de forma
    independiente — que el primero (elegido por orden condicion_iva/id) no la
    tenga delegada NO puede tirar abajo la consulta si otro emisor sí la
    tiene. resolver_persona reintenta con el siguiente antes de rendirse."""
    monkeypatch.setattr(
        "services.facturacion.emisores_repo.list_emisores",
        lambda conn: [_emisor(nombre="martin_santini"), _emisor(nombre="rambla")],
    )

    class _FakeCred:
        ambiente = "homologacion"
        cuit = 20300000000

    monkeypatch.setattr(
        "services.facturacion.config.credenciales", lambda emisor, conn: _FakeCred()
    )
    monkeypatch.setattr(
        "services.facturacion.wsaa_cache.get_ta",
        lambda emisor, conn, servicio=None: ("tok", "sign"),
    )

    from arca_fe.errores import ArcaResponseError

    class _FakePersona:
        razon_social = "Empresa XYZ"

    def _get_persona(self, cuit):
        # El emisor autenticador usado en esta consulta viaja en `self` vía
        # el `cuit_representada` con el que se construyó el PadronClient —
        # acá lo simulamos con un contador global simple. El primer emisor no
        # tiene la relación → `get_persona` levanta (ya no devuelve None); el
        # segundo la resuelve.
        _get_persona.calls += 1
        if _get_persona.calls == 1:
            raise ArcaResponseError("sin personaReturn", raw="x")
        return _FakePersona()

    _get_persona.calls = 0
    monkeypatch.setattr("arca_fe.padron.PadronClient.get_persona", _get_persona)

    result = resolver_persona("23373891029", conn=object())

    assert result.razon_social == "Empresa XYZ"
    assert _get_persona.calls == 2


def test_falla_real_levanta_runtime_error_con_motivo(monkeypatch):
    """AFIP caído / relación de padrón no delegada / cert vencido — NO se
    swallowea a None: eso diría "ARCA no tiene datos" cuando en realidad no
    pudimos ni preguntarle, imposible de diagnosticar desde afuera. Levanta
    RuntimeError con el motivo real; el route (admin-only) lo muestra tal
    cual — nunca rompe el formulario (sigue editable a mano), pero ya no
    miente sobre la causa."""
    monkeypatch.setattr(
        "services.facturacion.emisores_repo.list_emisores",
        lambda conn: [_emisor()],
    )
    monkeypatch.setattr(
        "services.facturacion.config.credenciales",
        lambda emisor, conn: (_ for _ in ()).throw(RuntimeError("cert vencido")),
    )
    with pytest.raises(RuntimeError, match="cert vencido"):
        resolver_persona("30712345678", conn=object())


def test_bloqueo_de_negocio_de_afip_se_propaga_con_el_texto_real(monkeypatch):
    """`get_persona` levanta ArcaBusinessError con el mensaje de negocio de
    AFIP en texto plano (ej. bloqueo por Domicilio Fiscal Electrónico, RG
    3990-E). resolver_persona lo captura y lo surfacea DENTRO del RuntimeError
    final (con el emisor + ambiente como contexto), preservando el texto de
    AFIP tal cual — que es el que el admin tiene que leer para actuar."""
    from arca_fe.errores import ArcaBusinessError

    monkeypatch.setattr(
        "services.facturacion.emisores_repo.list_emisores",
        lambda conn: [_emisor()],
    )

    class _FakeCred:
        ambiente = "homologacion"
        cuit = 20300000000

    monkeypatch.setattr(
        "services.facturacion.config.credenciales", lambda emisor, conn: _FakeCred()
    )
    monkeypatch.setattr(
        "services.facturacion.wsaa_cache.get_ta",
        lambda emisor, conn, servicio=None: ("tok", "sign"),
    )
    mensaje_afip = (
        "No consta en nuestros registros que Ud. ha cumplido con la adhesión "
        "al domicilio fiscal electrónico"
    )
    monkeypatch.setattr(
        "arca_fe.padron.PadronClient.get_persona",
        lambda self, cuit: (_ for _ in ()).throw(ArcaBusinessError(mensaje_afip)),
    )

    with pytest.raises(RuntimeError, match=mensaje_afip):
        resolver_persona("23373891029", conn=object())


@pytest.mark.parametrize(
    "prod,esperado",
    [(True, "PRODUCCIÓN"), (False, "HOMOLOGACIÓN")],
)
def test_mensaje_final_incluye_el_ambiente_en_que_consulto(monkeypatch, prod, esperado):
    """Cuando ningún emisor resuelve, el RuntimeError dice EN QUÉ AMBIENTE se
    consultó — el diagnóstico #1: si es homologación, cualquier CUIT real da
    'no existe' y no es un bug de datos."""
    from config import settings as app_settings
    from arca_fe.errores import ArcaResponseError

    monkeypatch.setattr(type(app_settings), "is_production", property(lambda self: prod))
    monkeypatch.setattr(
        "services.facturacion.emisores_repo.list_emisores",
        lambda conn: [_emisor(nombre="pablo")],
    )

    class _FakeCred:
        ambiente = "produccion" if prod else "homologacion"
        cuit = 20300000000

    monkeypatch.setattr(
        "services.facturacion.config.credenciales", lambda emisor, conn: _FakeCred()
    )
    monkeypatch.setattr(
        "services.facturacion.wsaa_cache.get_ta",
        lambda emisor, conn, servicio=None: ("tok", "sign"),
    )
    monkeypatch.setattr(
        "arca_fe.padron.PadronClient.get_persona",
        lambda self, cuit: (_ for _ in ()).throw(ArcaResponseError("x", raw="y")),
    )

    with pytest.raises(RuntimeError, match=esperado):
        resolver_persona("23373891029", conn=object())


# ── verificar_y_actualizar_receptor: SÍ bloquea la emisión (a diferencia de
# resolver_persona en el autocompletado, best-effort) ───────────────────────


class _FakeConnCliente:
    """Fake conn que soporta el SELECT de clientes de
    `_corregir_datos_facturacion_cliente` y captura los UPDATE emitidos
    (SQL + params) para inspeccionar qué se corrigió."""

    def __init__(self, row):
        self._row = row
        self.updates: list[tuple[str, tuple]] = []

    def execute(self, sql, params=None):
        sql_norm = " ".join(sql.split())
        if sql_norm.startswith("SELECT"):
            row = self._row

            class _R:
                def fetchone(self_inner):
                    return row

            return _R()
        self.updates.append((sql_norm, params))
        return None


def _persona_afip(
    razon_social="Empresa Nueva SA",
    domicilio="Calle Nueva 123",
    condicion_iva="responsable_inscripto",
):
    return PersonaArca(
        cuit="30712345678",
        razon_social=razon_social,
        nombre="",
        apellido="",
        domicilio=domicilio,
        condicion_iva=condicion_iva,
        estado_clave="ACTIVO",
    )


def test_verificar_receptor_corrige_solo_lo_que_difiere(monkeypatch):
    """Si el cliente ya tenía la misma condición IVA guardada pero razón
    social/domicilio distintos, el UPDATE toca SOLO esos dos — no reescribe
    lo que ya coincidía."""
    monkeypatch.setattr(
        "services.facturacion.padron.resolver_persona",
        lambda cuit, conn: _persona_afip(),
    )
    conn = _FakeConnCliente(
        row={
            "razon_social": "Empresa Vieja SA",
            "domicilio_fiscal": "Calle Vieja 1",
            "perfil_impuestos": "responsable_inscripto",  # ya coincide
        }
    )

    persona = verificar_y_actualizar_receptor("30712345678", cliente_id=7, conn=conn)

    assert persona.razon_social == "Empresa Nueva SA"
    assert len(conn.updates) == 1
    sql, params = conn.updates[0]
    assert "razon_social" in sql
    assert "domicilio_fiscal" in sql
    assert "perfil_impuestos" not in sql  # no tocado: ya coincidía
    assert params == ("Empresa Nueva SA", "Calle Nueva 123", 7)


def test_verificar_receptor_sin_diferencias_no_actualiza(monkeypatch):
    """Si todo ya coincide, no se emite ningún UPDATE."""
    monkeypatch.setattr(
        "services.facturacion.padron.resolver_persona",
        lambda cuit, conn: _persona_afip(),
    )
    conn = _FakeConnCliente(
        row={
            "razon_social": "Empresa Nueva SA",
            "domicilio_fiscal": "Calle Nueva 123",
            "perfil_impuestos": "responsable_inscripto",
        }
    )

    verificar_y_actualizar_receptor("30712345678", cliente_id=7, conn=conn)

    assert conn.updates == []


def test_verificar_receptor_nunca_toca_columnas_renaper(monkeypatch):
    """Regresión explícita: el UPDATE dinámico NUNCA debe poder tocar una
    columna `*_renaper` (esas son de Didit/KYC, dominio aparte) — solo las
    3 columnas de facturación explícitamente listadas."""
    monkeypatch.setattr(
        "services.facturacion.padron.resolver_persona",
        lambda cuit, conn: _persona_afip(),
    )
    conn = _FakeConnCliente(
        row={"razon_social": "X", "domicilio_fiscal": "Y", "perfil_impuestos": "Z"}
    )

    verificar_y_actualizar_receptor("30712345678", cliente_id=7, conn=conn)

    for sql, _params in conn.updates:
        assert "renaper" not in sql


def test_verificar_receptor_condicion_iva_vacia_bloquea(monkeypatch):
    """AFIP encontró la persona pero no pudo clasificar su condición IVA
    (raro) — ese dato SÍ se le manda a AFIP en el CAE (RG5616), así que
    bloquea con RuntimeError en vez de facturar con un valor sin confirmar.
    No se actualiza nada del cliente."""
    monkeypatch.setattr(
        "services.facturacion.padron.resolver_persona",
        lambda cuit, conn: _persona_afip(condicion_iva=""),
    )
    conn = _FakeConnCliente(row={"razon_social": "X", "domicilio_fiscal": "Y", "perfil_impuestos": "Z"})

    with pytest.raises(RuntimeError, match="condición IVA"):
        verificar_y_actualizar_receptor("30712345678", cliente_id=7, conn=conn)

    assert conn.updates == []


def test_verificar_receptor_propaga_falla_de_resolver_persona(monkeypatch):
    """Si AFIP no puede confirmar el CUIT en absoluto, `resolver_persona`
    levanta RuntimeError — `verificar_y_actualizar_receptor` NO lo atrapa,
    se propaga tal cual para que `emitir_factura` bloquee la emisión."""
    monkeypatch.setattr(
        "services.facturacion.padron.resolver_persona",
        lambda cuit, conn: (_ for _ in ()).throw(
            RuntimeError("No se pudo traer el padrón del CUIT — AFIP caída")
        ),
    )
    conn = _FakeConnCliente(row={"razon_social": "X", "domicilio_fiscal": "Y", "perfil_impuestos": "Z"})

    with pytest.raises(RuntimeError, match="AFIP caída"):
        verificar_y_actualizar_receptor("30712345678", cliente_id=7, conn=conn)


# ── verificar_y_crear_perfil_fiscal / verificar_y_crear_productora (#1240) ───


class _FakeConnPerfiles:
    """Fake conn para `verificar_y_crear_perfil_fiscal` — soporta el SELECT de
    "¿ya tiene algún perfil?", el upsert de `cliente_perfiles_fiscales`, y (si
    es el primer perfil) el UPDATE de `clientes.cuit` + el SELECT/UPDATE de
    `_corregir_datos_facturacion_cliente`."""

    def __init__(
        self,
        tiene_perfil_previo: bool,
        cliente_row: dict | None = None,
        perfil_existente_row: dict | None = None,
    ):
        self.tiene_perfil_previo = tiene_perfil_previo
        # Si no es None, simula que ESTE cuit puntual ya tiene una fila (para
        # el candado de re-verificar el propio default — ver test de abajo).
        self.perfil_existente_row = perfil_existente_row
        self.cliente_row = cliente_row or {
            "razon_social": None,
            "domicilio_fiscal": None,
            "perfil_impuestos": None,
        }
        self.perfil_inserts: list[tuple[str, tuple]] = []
        self.cliente_updates: list[tuple[str, tuple]] = []

    def execute(self, sql, params=None):
        sql_norm = " ".join(sql.split())

        class _R:
            def __init__(self_inner, row):
                self_inner._row = row

            def fetchone(self_inner):
                return self_inner._row

        if sql_norm.startswith("SELECT es_default FROM cliente_perfiles_fiscales"):
            return _R(self.perfil_existente_row)
        if sql_norm.startswith("SELECT 1 FROM cliente_perfiles_fiscales"):
            return _R({"1": 1} if self.tiene_perfil_previo else None)
        if sql_norm.startswith("INSERT INTO cliente_perfiles_fiscales"):
            self.perfil_inserts.append((sql_norm, params))
            return None
        if sql_norm.startswith("UPDATE clientes SET cuit"):
            self.cliente_updates.append((sql_norm, params))
            return None
        if sql_norm.startswith("SELECT razon_social, domicilio_fiscal, perfil_impuestos"):
            return _R(self.cliente_row)
        if sql_norm.startswith("UPDATE clientes SET"):
            self.cliente_updates.append((sql_norm, params))
            return None
        raise AssertionError(f"SQL inesperado: {sql_norm}")


def test_verificar_y_crear_perfil_fiscal_bloquea_si_afip_no_clasifica(monkeypatch):
    from services.facturacion.padron import verificar_y_crear_perfil_fiscal

    monkeypatch.setattr(
        "services.facturacion.padron.resolver_persona",
        lambda cuit, conn: _persona_afip(condicion_iva=""),
    )
    conn = _FakeConnPerfiles(tiene_perfil_previo=False)

    with pytest.raises(RuntimeError, match="condición IVA"):
        verificar_y_crear_perfil_fiscal("30712345678", cliente_id=7, conn=conn)

    assert conn.perfil_inserts == []


def test_verificar_y_crear_perfil_fiscal_primer_perfil_es_default_y_sincroniza_clientes(monkeypatch):
    """El primer perfil de un cliente se marca `es_default=TRUE` y ADEMÁS
    actualiza `clientes.cuit` + los campos de facturación (vía
    `_corregir_datos_facturacion_cliente`) — así el perfil default que siguen
    leyendo los call sites no tocados por esta iniciativa refleja el primero
    verificado."""
    from services.facturacion.padron import verificar_y_crear_perfil_fiscal

    monkeypatch.setattr(
        "services.facturacion.padron.resolver_persona",
        lambda cuit, conn: _persona_afip(),
    )
    conn = _FakeConnPerfiles(tiene_perfil_previo=False)

    persona = verificar_y_crear_perfil_fiscal("30712345678", cliente_id=7, conn=conn)

    assert persona.razon_social == "Empresa Nueva SA"
    assert len(conn.perfil_inserts) == 1
    _, params = conn.perfil_inserts[0]
    assert params[-1] is True  # es_default
    # se sincronizó `clientes` (cuit + los 3 campos de facturación)
    assert any("UPDATE clientes SET cuit" in sql for sql, _ in conn.cliente_updates)
    assert any("razon_social" in sql for sql, _ in conn.cliente_updates)


def test_verificar_y_crear_perfil_fiscal_segundo_perfil_no_pisa_default(monkeypatch):
    """Si el cliente YA tiene un perfil, el nuevo NO se marca default ni toca
    `clientes` — solo se agrega a la lista."""
    from services.facturacion.padron import verificar_y_crear_perfil_fiscal

    monkeypatch.setattr(
        "services.facturacion.padron.resolver_persona",
        lambda cuit, conn: _persona_afip(),
    )
    conn = _FakeConnPerfiles(tiene_perfil_previo=True)

    verificar_y_crear_perfil_fiscal("30712345678", cliente_id=7, conn=conn, etiqueta="Productora X")

    _, params = conn.perfil_inserts[0]
    assert params[-1] is False  # es_default
    assert conn.cliente_updates == []


def test_verificar_y_crear_perfil_fiscal_reverificar_el_propio_default_sincroniza_clientes(monkeypatch):
    """Bug real (encontrado en revisión): reverificar el CUIT que YA es el
    default del cliente tiene que seguir sincronizando `clientes.*` con los
    datos frescos de AFIP — antes, `ya_tiene_perfil` encontraba ESE MISMO
    perfil y computaba `es_default=False` (porque "el cliente ya tiene un
    perfil"), salteando el sync aunque siguiera siendo el default real."""
    from services.facturacion.padron import verificar_y_crear_perfil_fiscal

    monkeypatch.setattr(
        "services.facturacion.padron.resolver_persona",
        lambda cuit, conn: _persona_afip(razon_social="Nombre Actualizado SA"),
    )
    # Este CUIT YA existe como perfil, y YA es el default.
    conn = _FakeConnPerfiles(tiene_perfil_previo=True, perfil_existente_row={"es_default": True})

    verificar_y_crear_perfil_fiscal("30712345678", cliente_id=7, conn=conn)

    _, params = conn.perfil_inserts[0]
    assert params[-1] is True  # es_default sigue TRUE en el upsert
    # Y el sync a `clientes` (cuit + razón social/domicilio/perfil) SÍ corre.
    assert any("UPDATE clientes SET cuit" in sql for sql, _ in conn.cliente_updates)
    assert any("razon_social" in sql for sql, _ in conn.cliente_updates)


def test_verificar_y_crear_perfil_fiscal_reverificar_perfil_no_default_no_sincroniza(monkeypatch):
    """Reverificar un CUIT que YA existe pero NO es el default no debe tocar
    `clientes` — solo refresca su propia fila."""
    from services.facturacion.padron import verificar_y_crear_perfil_fiscal

    monkeypatch.setattr(
        "services.facturacion.padron.resolver_persona",
        lambda cuit, conn: _persona_afip(),
    )
    conn = _FakeConnPerfiles(tiene_perfil_previo=True, perfil_existente_row={"es_default": False})

    verificar_y_crear_perfil_fiscal("30712345678", cliente_id=7, conn=conn)

    _, params = conn.perfil_inserts[0]
    assert params[-1] is False
    assert conn.cliente_updates == []


class _FakeConnProductoras:
    def __init__(self):
        self.inserts: list[tuple[str, tuple]] = []

    def execute(self, sql, params=None):
        sql_norm = " ".join(sql.split())
        if sql_norm.startswith("INSERT INTO productoras"):
            self.inserts.append((sql_norm, params))
            return None
        raise AssertionError(f"SQL inesperado: {sql_norm}")


def test_verificar_y_crear_productora_bloquea_si_afip_no_clasifica(monkeypatch):
    from services.facturacion.padron import verificar_y_crear_productora

    monkeypatch.setattr(
        "services.facturacion.padron.resolver_persona",
        lambda cuit, conn: _persona_afip(condicion_iva=""),
    )
    conn = _FakeConnProductoras()

    with pytest.raises(RuntimeError, match="condición IVA"):
        verificar_y_crear_productora("30712345678", conn=conn)

    assert conn.inserts == []


def test_verificar_y_crear_productora_upsert_por_cuit(monkeypatch):
    from services.facturacion.padron import verificar_y_crear_productora

    monkeypatch.setattr(
        "services.facturacion.padron.resolver_persona",
        lambda cuit, conn: _persona_afip(),
    )
    conn = _FakeConnProductoras()

    persona = verificar_y_crear_productora("30712345678", conn=conn, notas="Ref: rodaje X")

    assert persona.razon_social == "Empresa Nueva SA"
    assert len(conn.inserts) == 1
    _, params = conn.inserts[0]
    assert params == ("30712345678", "responsable_inscripto", "Empresa Nueva SA", "Calle Nueva 123", "Ref: rodaje X")
