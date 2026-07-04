"""Tests de arca_fe.padron — sin red. Mockea la respuesta de zeep para el
padrón A5 (Constancia de Inscripción), prueba el parseo de persona
física/jurídica, monotributo/RI/exento, y que un CUIT sin datos (o un fault
de AFIP) levante el motivo tipado real (ArcaBusinessError con el texto de AFIP,
o ArcaResponseError con la respuesta cruda) — NUNCA un None mudo.

Los idImpuesto (30=RI, 32=Exento) están verificados contra pyafipws — el
código viejo los tenía invertidos (32 disparaba "responsable_inscripto"),
lo que habría detectado un cliente EXENTO como RI.

**Disciplina de mock (regresión #personaReturn):** la respuesta de nivel
superior se mockea con `spec=["personaReturn"]` — el nombre del campo real
del WSDL `getPersonaResponse`. Un `MagicMock()` SIN spec auto-genera
cualquier atributo que se le pida, así que un test podía "pasar" leyendo el
campo equivocado (`resp.persona`, que no existe en la respuesta real) sin que
nada lo notara — que es precisamente cómo se coló el bug de prod. Con spec, si
el código lee un campo que AFIP no manda, el mock levanta `AttributeError` en
vez de fabricar un objeto fantasma."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _persona_juridica(
    razon_social="Empresa XYZ SRL", id_impuesto=30, estado_clave="ACTIVO"
):
    persona = MagicMock(
        spec=["datosGenerales", "datosRegimenGeneral", "datosMonotributo"]
    )
    dg = MagicMock()
    dg.razonSocial = razon_social
    dg.estadoClave = estado_clave
    dom = MagicMock()
    dom.direccion = "Ruta 88 km 12"
    dom.localidad = "Mar del Plata"
    dom.descripcionProvincia = "Buenos Aires"
    dg.domicilioFiscal = dom
    persona.datosGenerales = dg
    persona.datosMonotributo = None

    if id_impuesto is not None:
        dr = MagicMock()
        imp = MagicMock()
        imp.idImpuesto = id_impuesto
        dr.impuesto = [imp]
        persona.datosRegimenGeneral = dr
    else:
        persona.datosRegimenGeneral = None
    return persona


def _persona_fisica_monotributo(nombre="Juan", apellido="Pérez", estado_clave="ACTIVO"):
    persona = MagicMock(
        spec=["datosGenerales", "datosMonotributo", "datosRegimenGeneral"]
    )
    dg = MagicMock()
    dg.razonSocial = ""
    dg.nombre = nombre
    dg.apellido = apellido
    dg.estadoClave = estado_clave
    dg.domicilioFiscal = None
    persona.datosGenerales = dg
    persona.datosMonotributo = MagicMock()
    persona.datosRegimenGeneral = None
    return persona


def test_get_persona_juridica_responsable_inscripto():
    from arca_fe.padron import PadronClient

    client = PadronClient("awshomo.afip.gov.ar", 20123456789, "tok", "sig")
    resp = MagicMock(spec=["personaReturn"])
    resp.personaReturn = _persona_juridica(id_impuesto=30)

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.getPersona.return_value = resp
        mock_client_fn.return_value.service = mock_service

        result = client.get_persona("30-71234567-8")

    assert result is not None
    assert result.razon_social == "Empresa XYZ SRL"
    assert "Ruta 88 km 12" in result.domicilio
    assert result.condicion_iva == "responsable_inscripto"


def test_get_persona_ri_expone_tipo_persona_e_impuestos_tal_cual():
    """Además de derivar `condicion_iva`, el motor expone `tipo_persona` y el
    tuple `impuestos` con TODOS los impuestos que AFIP reporta (con su estado
    activo/baja) — útil para diagnosticar si la relación de IVA está
    REALMENTE activa en AFIP, no solo inferirlo de un id."""
    from arca_fe.padron import PadronClient

    client = PadronClient("awshomo.afip.gov.ar", 20123456789, "tok", "sig")

    dg = MagicMock()
    dg.razonSocial = "Empresa XYZ SRL"
    dg.estadoClave = "ACTIVO"
    dg.domicilioFiscal = None
    dg.tipoPersona = "JURIDICA"

    imp_iva = MagicMock()
    imp_iva.idImpuesto = 30
    imp_iva.descripcionImpuesto = "IVA"
    imp_iva.estadoImpuesto = "AC"
    imp_iva.periodo = 202001

    imp_ganancias = MagicMock()
    imp_ganancias.idImpuesto = 11
    imp_ganancias.descripcionImpuesto = "Ganancias Sociedades"
    imp_ganancias.estadoImpuesto = "BA"
    imp_ganancias.periodo = 201901

    dr = MagicMock()
    dr.impuesto = [imp_iva, imp_ganancias]
    dr.actividad = []

    persona = MagicMock(
        spec=["datosGenerales", "datosMonotributo", "datosRegimenGeneral"]
    )
    persona.datosGenerales = dg
    persona.datosMonotributo = None
    persona.datosRegimenGeneral = dr

    resp = MagicMock(spec=["personaReturn"])
    resp.personaReturn = persona

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.getPersona.return_value = resp
        mock_client_fn.return_value.service = mock_service

        result = client.get_persona("30712345678")

    assert result.condicion_iva == "responsable_inscripto"
    assert result.tipo_persona == "JURIDICA"
    vistos = {(i.descripcion, i.estado) for i in result.impuestos}
    assert ("IVA", "AC") in vistos
    assert ("Ganancias Sociedades", "BA") in vistos


def test_get_persona_monotributo_categoria_y_actividad():
    """Monotributista: `categoria_monotributo` y `actividades` (CLAE) se
    exponen además de `condicion_iva='monotributo'`."""
    from arca_fe.padron import PadronClient

    client = PadronClient("awshomo.afip.gov.ar", 20123456789, "tok", "sig")

    dg = MagicMock()
    dg.razonSocial = ""
    dg.nombre = "Juan"
    dg.apellido = "Pérez"
    dg.estadoClave = "ACTIVO"
    dg.domicilioFiscal = None
    dg.tipoPersona = "FISICA"

    categoria = MagicMock()
    categoria.descripcionCategoria = "Categoría B"

    act1 = MagicMock()
    act1.idActividad = 620100
    act1.descripcionActividad = "Servicios de consultores en informática"
    act1.periodo = 202301
    act1.orden = 1

    imp1 = MagicMock()
    imp1.idImpuesto = 20
    imp1.descripcionImpuesto = "Monotributo"
    imp1.estadoImpuesto = "AC"
    imp1.periodo = 202301

    dm = MagicMock()
    dm.categoriaMonotributo = categoria
    dm.actividad = [act1]
    dm.actividadMonotributista = None
    dm.impuesto = [imp1]

    persona = MagicMock(
        spec=["datosGenerales", "datosMonotributo", "datosRegimenGeneral"]
    )
    persona.datosGenerales = dg
    persona.datosMonotributo = dm
    persona.datosRegimenGeneral = None

    resp = MagicMock(spec=["personaReturn"])
    resp.personaReturn = persona

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.getPersona.return_value = resp
        mock_client_fn.return_value.service = mock_service

        result = client.get_persona("20301234567")

    assert result.condicion_iva == "monotributo"
    assert result.tipo_persona == "FISICA"
    assert result.categoria_monotributo == "Categoría B"
    assert len(result.actividades) == 1
    assert result.actividades[0].descripcion == "Servicios de consultores en informática"
    assert len(result.impuestos) == 1
    assert result.impuestos[0].descripcion == "Monotributo"
    assert result.impuestos[0].estado == "AC"


def test_get_persona_juridica_exento():
    """idImpuesto=32 es EXENTO, no responsable inscripto — regresión del bug
    donde estaban invertidos."""
    from arca_fe.padron import PadronClient

    client = PadronClient("awshomo.afip.gov.ar", 20123456789, "tok", "sig")
    resp = MagicMock(spec=["personaReturn"])
    resp.personaReturn = _persona_juridica(id_impuesto=32)

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.getPersona.return_value = resp
        mock_client_fn.return_value.service = mock_service

        result = client.get_persona("30-71234567-8")

    assert result.condicion_iva == "exento"


def test_get_persona_expone_estado_clave():
    from arca_fe.padron import PadronClient

    client = PadronClient("awshomo.afip.gov.ar", 20123456789, "tok", "sig")
    resp = MagicMock(spec=["personaReturn"])
    resp.personaReturn = _persona_juridica(estado_clave="INACTIVO")

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.getPersona.return_value = resp
        mock_client_fn.return_value.service = mock_service

        result = client.get_persona("30-71234567-8")

    assert result.estado_clave == "INACTIVO"


def test_get_persona_fisica_monotributo_arma_nombre_completo():
    from arca_fe.padron import PadronClient

    client = PadronClient("awshomo.afip.gov.ar", 20123456789, "tok", "sig")
    resp = MagicMock(spec=["personaReturn"])
    resp.personaReturn = _persona_fisica_monotributo()

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.getPersona.return_value = resp
        mock_client_fn.return_value.service = mock_service

        result = client.get_persona("20301234567")

    assert result.razon_social == "Juan Pérez"
    assert result.condicion_iva == "monotributo"
    assert result.domicilio == ""


def test_get_persona_fisica_expone_nombre_y_apellido_por_separado():
    """Un formulario con campos Nombre/Apellido separados (cliente) no tiene
    que quedarse solo con el combinado — AFIP los da separados, no hay que
    tirarlos."""
    from arca_fe.padron import PadronClient

    client = PadronClient("awshomo.afip.gov.ar", 20123456789, "tok", "sig")
    resp = MagicMock(spec=["personaReturn"])
    resp.personaReturn = _persona_fisica_monotributo(nombre="Juan", apellido="Pérez")

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.getPersona.return_value = resp
        mock_client_fn.return_value.service = mock_service

        result = client.get_persona("20301234567")

    assert result.nombre == "Juan"
    assert result.apellido == "Pérez"


def test_get_persona_juridica_no_tiene_nombre_ni_apellido_separado():
    """Una empresa solo tiene razón social — no hay Nombre/Apellido que
    inventar."""
    from arca_fe.padron import PadronClient

    client = PadronClient("awshomo.afip.gov.ar", 20123456789, "tok", "sig")
    resp = MagicMock(spec=["personaReturn"])
    resp.personaReturn = _persona_juridica()

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.getPersona.return_value = resp
        mock_client_fn.return_value.service = mock_service

        result = client.get_persona("30-71234567-8")

    assert result.nombre == ""
    assert result.apellido == ""


def test_get_persona_sin_personaReturn_levanta_response_error_con_crudo():
    """`personaReturn` None (AFIP devolvió una respuesta sin ese nodo) YA NO es
    un None mudo: levanta ArcaResponseError con la respuesta cruda en `.raw`
    para poder diagnosticar qué mandó AFIP en vez de "sin datos ni motivo"."""
    from arca_fe.padron import PadronClient
    from arca_fe.errores import ArcaResponseError

    client = PadronClient("awshomo.afip.gov.ar", 20123456789, "tok", "sig")
    resp = MagicMock(spec=["personaReturn"])
    resp.personaReturn = None

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.getPersona.return_value = resp
        mock_client_fn.return_value.service = mock_service

        with pytest.raises(ArcaResponseError, match="datos de persona") as ei:
            client.get_persona("20999999999")

    assert ei.value.raw


def test_get_persona_bloqueada_por_regla_de_negocio_levanta_con_motivo():
    """AFIP conoce el CUIT pero bloquea la constancia por una regla propia
    (ej. RG 3990-E, sin adhesión a Domicilio Fiscal Electrónico) — la
    respuesta viene SIN datosGenerales pero CON errorConstancia poblado
    (manual "WS_SR_constancia_inscripcion" §5.3). Antes esto se leía igual
    que "el CUIT no existe"; ahora levanta ArcaBusinessError con el motivo
    real de AFIP y sus mensajes estructurados en `.errores`."""
    from arca_fe.padron import PadronClient
    from arca_fe.errores import ArcaBusinessError

    client = PadronClient("awshomo.afip.gov.ar", 20123456789, "tok", "sig")
    persona = MagicMock(
        spec=[
            "datosGenerales",
            "errorConstancia",
            "errorRegimenGeneral",
            "errorMonotributo",
        ]
    )
    persona.datosGenerales = None
    persona.errorRegimenGeneral = None
    persona.errorMonotributo = None
    err = MagicMock()
    err.error = "No consta en nuestros registros que Ud. ha cumplido con la adhesión al domicilio fiscal electrónico"
    persona.errorConstancia = err
    resp = MagicMock(spec=["personaReturn"])
    resp.personaReturn = persona

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.getPersona.return_value = resp
        mock_client_fn.return_value.service = mock_service

        with pytest.raises(
            ArcaBusinessError, match="domicilio fiscal electrónico"
        ) as ei:
            client.get_persona("23373891029")

    assert ei.value.errores == ((None, err.error),)


def test_get_persona_sin_datosgenerales_ni_error_levanta_response_error_con_crudo():
    """Sin datosGenerales Y sin ningún error* poblado — no hay un motivo de
    negocio que mostrar, pero YA NO se degrada a None mudo: levanta
    ArcaResponseError con la respuesta cruda en `.raw` (AFIP contestó algo que
    no sabemos interpretar — mostrarlo es más honesto que "sin datos")."""
    from arca_fe.padron import PadronClient
    from arca_fe.errores import ArcaResponseError

    client = PadronClient("awshomo.afip.gov.ar", 20123456789, "tok", "sig")
    persona = MagicMock(
        spec=[
            "datosGenerales",
            "errorConstancia",
            "errorRegimenGeneral",
            "errorMonotributo",
        ]
    )
    persona.datosGenerales = None
    persona.errorConstancia = None
    persona.errorRegimenGeneral = None
    persona.errorMonotributo = None
    resp = MagicMock(spec=["personaReturn"])
    resp.personaReturn = persona

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.getPersona.return_value = resp
        mock_client_fn.return_value.service = mock_service

        with pytest.raises(ArcaResponseError, match="datosGenerales") as ei:
            client.get_persona("23373891029")

    assert ei.value.raw


def test_error_constancia_como_lista_surfacea_el_motivo():
    """AFIP suele mandar `errorConstancia` como ARRAY (`ArrayOfString`), no como
    objeto con `.error` — esta es la forma que ANTES se perdía (el parser leía
    `.error` de la lista → None → 'sin motivo' espurio). Ahora el motivo real
    ('No existe persona con ese id') se surfacea como ArcaBusinessError."""
    from arca_fe.padron import PadronClient
    from arca_fe.errores import ArcaBusinessError

    client = PadronClient("awshomo.afip.gov.ar", 20123456789, "tok", "sig")
    persona = MagicMock(
        spec=[
            "datosGenerales",
            "errorConstancia",
            "errorRegimenGeneral",
            "errorMonotributo",
        ]
    )
    persona.datosGenerales = None
    persona.errorConstancia = ["No existe persona con ese id"]
    persona.errorRegimenGeneral = None
    persona.errorMonotributo = None
    resp = MagicMock(spec=["personaReturn"])
    resp.personaReturn = persona

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.getPersona.return_value = resp
        mock_client_fn.return_value.service = mock_service

        with pytest.raises(ArcaBusinessError, match="No existe persona") as ei:
            client.get_persona("23373891029")

    assert ei.value.errores == ((None, "No existe persona con ese id"),)


def test_error_constancia_como_lista_de_objetos_con_error():
    """`errorConstancia` como lista de objetos con `.error` (otra forma que AFIP
    puede mandar) — se aplanan todos los mensajes."""
    from arca_fe.padron import PadronClient
    from arca_fe.errores import ArcaBusinessError

    client = PadronClient("awshomo.afip.gov.ar", 20123456789, "tok", "sig")
    e1 = MagicMock()
    e1.error = "Motivo uno"
    e2 = MagicMock()
    e2.error = "Motivo dos"
    persona = MagicMock(
        spec=[
            "datosGenerales",
            "errorConstancia",
            "errorRegimenGeneral",
            "errorMonotributo",
        ]
    )
    persona.datosGenerales = None
    persona.errorConstancia = [e1, e2]
    persona.errorRegimenGeneral = None
    persona.errorMonotributo = None
    resp = MagicMock(spec=["personaReturn"])
    resp.personaReturn = persona

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.getPersona.return_value = resp
        mock_client_fn.return_value.service = mock_service

        with pytest.raises(ArcaBusinessError, match="Motivo uno; Motivo dos"):
            client.get_persona("23373891029")


def test_error_constancia_como_string_suelto():
    """`errorConstancia` como string directo — también se surfacea."""
    from arca_fe.padron import PadronClient
    from arca_fe.errores import ArcaBusinessError

    client = PadronClient("awshomo.afip.gov.ar", 20123456789, "tok", "sig")
    persona = MagicMock(
        spec=[
            "datosGenerales",
            "errorConstancia",
            "errorRegimenGeneral",
            "errorMonotributo",
        ]
    )
    persona.datosGenerales = None
    persona.errorConstancia = "Clave fiscal inactiva"
    persona.errorRegimenGeneral = None
    persona.errorMonotributo = None
    resp = MagicMock(spec=["personaReturn"])
    resp.personaReturn = persona

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.getPersona.return_value = resp
        mock_client_fn.return_value.service = mock_service

        with pytest.raises(ArcaBusinessError, match="Clave fiscal inactiva"):
            client.get_persona("23373891029")


def test_get_persona_fault_levanta_con_el_texto_de_afip():
    """Regresión: ANTES se filtraban por substring los Fault que mencionaban
    "no se encuentran datos"/"sin resultados", tratándolos como silencio
    limpio (None) — eso escondía motivos reales indistinguibles entre sí (un
    CUIT real bloqueado por WSAA/relación/cert se leía IGUAL que un CUIT
    inexistente). Ahora CUALQUIER Fault levanta ArcaResponseError con el texto
    de AFIP tal cual (en el mensaje y en `.raw`), sin heurística de por medio."""
    import zeep.exceptions
    from arca_fe.padron import PadronClient
    from arca_fe.errores import ArcaResponseError

    client = PadronClient("awshomo.afip.gov.ar", 20123456789, "tok", "sig")

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.getPersona.side_effect = zeep.exceptions.Fault(
            "No se encuentran datos referentes al contribuyente consultado"
        )
        mock_client_fn.return_value.service = mock_service

        with pytest.raises(ArcaResponseError, match="No se encuentran datos") as ei:
            client.get_persona("20999999999")

    assert "No se encuentran datos" in ei.value.raw


def test_get_persona_fault_desconocido_tambien_levanta_con_su_texto():
    import zeep.exceptions
    from arca_fe.padron import PadronClient
    from arca_fe.errores import ArcaResponseError

    client = PadronClient("awshomo.afip.gov.ar", 20123456789, "tok", "sig")

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.getPersona.side_effect = zeep.exceptions.Fault(
            "coe.alreadyAuthenticated"
        )
        mock_client_fn.return_value.service = mock_service

        with pytest.raises(ArcaResponseError, match="coe.alreadyAuthenticated"):
            client.get_persona("20999999999")


# ── _get_client: usa el endpoint tal cual, sin URLs propias duplicadas ──────


def test_get_client_usa_el_endpoint_tal_cual_y_lo_cachea(monkeypatch):
    """Mismo criterio que arca_fe.wsfe: `endpoint` es la URL completa del
    WSDL ya resuelta por el caller — sin copia propia de homologación/
    producción ni matching de substring para elegir."""
    from arca_fe import padron

    monkeypatch.setattr(padron, "_CLIENT_CACHE", {})
    calls = []

    class _FakeZeepClient:
        def __init__(self, wsdl, transport=None):
            calls.append(wsdl)

    monkeypatch.setattr(padron.zeep, "Client", _FakeZeepClient)

    cliente1 = padron._get_client("https://ejemplo-cualquiera.test/wsdl", 20.0)
    cliente2 = padron._get_client("https://ejemplo-cualquiera.test/wsdl", 20.0)

    assert calls == ["https://ejemplo-cualquiera.test/wsdl"]
    assert cliente1 is cliente2


def test_get_client_no_colisiona_entre_timeouts_distintos(monkeypatch):
    from arca_fe import padron

    monkeypatch.setattr(padron, "_CLIENT_CACHE", {})
    calls = []

    class _FakeZeepClient:
        def __init__(self, wsdl, transport=None):
            calls.append(wsdl)

    monkeypatch.setattr(padron.zeep, "Client", _FakeZeepClient)

    cliente_20 = padron._get_client("https://ejemplo.test/wsdl", 20.0)
    cliente_40 = padron._get_client("https://ejemplo.test/wsdl", 40.0)

    assert cliente_20 is not cliente_40
    assert len(calls) == 2


def test_padron_clear_cache_limpia_de_verdad(monkeypatch):
    from arca_fe import padron

    monkeypatch.setattr(padron, "_CLIENT_CACHE", {})
    monkeypatch.setattr(padron.zeep, "Client", lambda wsdl, transport=None: object())

    padron._get_client("https://ejemplo.test/wsdl", 20.0)
    assert padron._CLIENT_CACHE

    padron.clear_cache()

    assert padron._CLIENT_CACHE == {}


def test_padron_client_timeout_configurable_por_instancia():
    from arca_fe.padron import PadronClient

    client_default = PadronClient("wswhomo.afip.gov.ar", 20301234563, "tok", "sig")
    client_custom = PadronClient("wswhomo.afip.gov.ar", 20301234563, "tok", "sig", timeout=40.0)

    assert client_default.timeout == 20.0
    assert client_custom.timeout == 40.0


# ── Regresión #personaReturn: la respuesta cruda del WSDL real ──────────────


def test_lee_personaReturn_de_una_respuesta_con_la_forma_real_del_wsdl():
    """Con `SimpleNamespace` (no MagicMock: NO fabrica atributos inexistentes)
    imitando la forma real de `getPersonaResponse` — el dato viaja en
    `personaReturn`, NO en `persona`. Si el código volviera a leer el campo
    equivocado, `getattr(resp, "personaReturn", None)` daría None y este test
    fallaría con un `assert ... is not None` — el bug ya no puede degradar a
    "sin datos" en silencio."""
    from arca_fe.padron import PadronClient

    resp = SimpleNamespace(
        personaReturn=SimpleNamespace(
            datosGenerales=SimpleNamespace(
                razonSocial="Rambla SRL",
                nombre="",
                apellido="",
                estadoClave="ACTIVO",
                domicilioFiscal=None,
            ),
            datosMonotributo=None,
            datosRegimenGeneral=None,
            errorConstancia=None,
            errorMonotributo=None,
            errorRegimenGeneral=None,
        )
    )
    client = PadronClient("https://x", 20300000000, "t", "s")

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.getPersona.return_value = resp
        mock_client_fn.return_value.service = mock_service

        persona = client.get_persona("23373891029")

    assert persona is not None
    assert persona.razon_social == "Rambla SRL"
    assert persona.estado_clave == "ACTIVO"


def test_get_persona_respuesta_desenvuelta_sin_wrapper():
    """Si el cliente SOAP DESENVUELVE el retorno (resp ES la persona, con
    `datosGenerales` directo y SIN `.personaReturn`), igual se parsea — no se
    depende solo de `.personaReturn`, que contra la respuesta real de AFIP en
    prod venía vacío."""
    from arca_fe.padron import PadronClient

    resp = SimpleNamespace(
        datosGenerales=SimpleNamespace(
            razonSocial="Rambla SRL",
            nombre="",
            apellido="",
            estadoClave="ACTIVO",
            domicilioFiscal=None,
        ),
        datosMonotributo=None,
        datosRegimenGeneral=None,
        errorConstancia=None,
        errorMonotributo=None,
        errorRegimenGeneral=None,
    )
    client = PadronClient("https://x", 20300000000, "t", "s")

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.getPersona.return_value = resp
        mock_client_fn.return_value.service = mock_service

        persona = client.get_persona("30712345678")

    assert persona.razon_social == "Rambla SRL"
    assert persona.estado_clave == "ACTIVO"


def test_respuesta_sin_personaReturn_levanta_response_error():
    """`resp` sin el campo `personaReturn` (con `SimpleNamespace`, que NO
    fabrica atributos) — YA NO devuelve None mudo: levanta ArcaResponseError
    con la respuesta cruda, para dejar de esconder qué contestó AFIP."""
    from arca_fe.padron import PadronClient
    from arca_fe.errores import ArcaResponseError

    resp = SimpleNamespace()
    client = PadronClient("https://x", 20300000000, "t", "s")

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.getPersona.return_value = resp
        mock_client_fn.return_value.service = mock_service

        with pytest.raises(ArcaResponseError):
            client.get_persona("23373891029")
