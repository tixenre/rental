"""Tests de la extracción de datos de RENAPER del `decision` de Didit (API v3).

Pieza pura (sin DB ni red): `extraer_datos_renaper(decision) -> DatosRenaper`.
Cubre el shape v3 real (arrays plurales `id_verifications[]`), los fallbacks de
CUIL/dirección, la elección de la entrada Approved y la tolerancia a payloads
incompletos o malformados (el webhook nunca debe romper → siempre 200).
"""

import pytest

from services.didit.decision import DatosRenaper, extraer_datos_renaper

pytestmark = pytest.mark.unit


# Payload v3 realista (Argentina / RENAPER vía Didit). La data vive en
# `decision.id_verifications[]`, NO en un `kyc.document` singular (shape viejo).
_DECISION_AR = {
    "id_verifications": [
        {
            "node_id": "id_verification_1",
            "status": "Approved",
            "document_type": "Identity Card",
            "document_number": "12345678",
            "personal_number": "20-12345678-9",
            "first_name": "Juan",
            "last_name": "Pérez García",
            "full_name": "Juan Carlos Pérez García",
            "date_of_birth": "1990-05-15",
            "gender": "M",
            "nationality": "ARG",
            "issuing_state": "ARG",
            "address": "Av. Corrientes 1234, CABA",
            "formatted_address": "Av. Corrientes 1234, C1043 CABA, Argentina",
            "expiration_date": "2031-06-02",
            "portrait_image": "https://didit.example/portrait.jpg",
        }
    ],
    "face_matches": [{"node_id": "face_1", "status": "Approved", "score": 98.5}],
    "liveness_checks": [{"node_id": "liveness_1", "status": "Approved", "score": 99.1}],
}


def test_extrae_todos_los_campos():
    d = extraer_datos_renaper(_DECISION_AR)
    assert d.dni == "12345678"
    assert d.cuil == "20-12345678-9"
    assert d.nombre == "Juan"
    assert d.apellido == "Pérez García"
    assert d.nombre_completo == "Juan Carlos Pérez García"
    assert d.fecha_nacimiento == "1990-05-15"
    assert d.direccion == "Av. Corrientes 1234, C1043 CABA, Argentina"
    assert d.tiene_datos is True


def test_no_extrae_imagen_ni_biometrico():
    """Ley 25.326: NO se extraen URLs de imagen ni scores biométricos."""
    d = extraer_datos_renaper(_DECISION_AR)
    valores = (d.dni, d.cuil, d.nombre, d.apellido, d.nombre_completo,
               d.fecha_nacimiento, d.direccion)
    assert not any(v and "http" in v for v in valores if v)


def test_cuil_desde_personal_number():
    d = extraer_datos_renaper(
        {"id_verifications": [{"document_number": "1", "personal_number": "20-1-9"}]}
    )
    assert d.cuil == "20-1-9"


def test_cuil_fallback_tax_id_y_cuil():
    """Si no hay personal_number, cae a tax_id; y a `cuil` como último recurso."""
    d_tax = extraer_datos_renaper(
        {"id_verifications": [{"document_number": "1", "tax_id": "27-2-3"}]}
    )
    assert d_tax.cuil == "27-2-3"
    d_cuil = extraer_datos_renaper(
        {"id_verifications": [{"document_number": "1", "cuil": "23-4-5"}]}
    )
    assert d_cuil.cuil == "23-4-5"


def test_direccion_fallback_address():
    """Sin formatted_address se usa `address`."""
    d = extraer_datos_renaper(
        {"id_verifications": [{"document_number": "1", "address": "Calle Falsa 123"}]}
    )
    assert d.direccion == "Calle Falsa 123"


def test_prefiere_entrada_approved():
    """Con varias entradas, elige la Approved con número de documento."""
    decision = {
        "id_verifications": [
            {"status": "Declined", "document_number": "999", "full_name": "Viejo"},
            {"status": "Approved", "document_number": "12345678", "full_name": "Bueno"},
        ]
    }
    d = extraer_datos_renaper(decision)
    assert d.dni == "12345678"
    assert d.nombre_completo == "Bueno"


def test_sin_approved_usa_primera_con_documento():
    """Si ninguna está Approved, toma la primera con número de documento."""
    decision = {
        "id_verifications": [
            {"status": "InReview", "document_number": "555", "full_name": "Único"},
        ]
    }
    d = extraer_datos_renaper(decision)
    assert d.dni == "555"
    assert d.nombre_completo == "Único"


def test_ignora_entradas_malformadas():
    """Entradas no-dict o sin document_number se ignoran sin romper."""
    decision = {
        "id_verifications": [
            "no soy un dict",
            {"status": "Approved"},  # sin document_number
            None,
            {"document_number": "  ", "full_name": "vacío"},  # número en blanco
            {"document_number": "777", "full_name": "Válido"},
        ]
    }
    d = extraer_datos_renaper(decision)
    assert d.dni == "777"
    assert d.nombre_completo == "Válido"


def test_strip_y_campos_vacios():
    """Espacios se recortan; vacíos → None (no string vacío)."""
    d = extraer_datos_renaper(
        {"id_verifications": [{"document_number": "  42  ", "first_name": "   ",
                               "last_name": "Gómez"}]}
    )
    assert d.dni == "42"
    assert d.nombre is None
    assert d.apellido == "Gómez"


@pytest.mark.parametrize("decision", [None, {}, {"id_verifications": []},
                                      {"id_verifications": "no-es-lista"},
                                      {"otra_cosa": 1}, "no-soy-dict", 42])
def test_payload_incompleto_o_invalido_no_rompe(decision):
    """Payloads ausentes/incompletos/inesperados → DatosRenaper vacío, no excepción.
    Es lo que dispara el respaldo retrieve_decision en el route."""
    d = extraer_datos_renaper(decision)
    assert d == DatosRenaper()
    assert d.tiene_datos is False
