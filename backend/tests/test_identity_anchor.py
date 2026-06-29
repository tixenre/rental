"""Tests del ancla CUIL — normalización + validación mod-11 (puro, sin DB)."""
import pytest

from identity.anchor import cuil_valido, normalizar_cuil

pytestmark = pytest.mark.unit


def test_normaliza_a_11_digitos():
    assert normalizar_cuil("20-12345678-6") == "20123456786"
    assert normalizar_cuil("20123456786") == "20123456786"
    assert normalizar_cuil("  20 12345678 6 ") == "20123456786"


def test_normaliza_rechaza_largo_incorrecto():
    assert normalizar_cuil("123") is None
    assert normalizar_cuil("201234567890123") is None
    assert normalizar_cuil("") is None
    assert normalizar_cuil(None) is None


def test_cuil_valido_mod11():
    # Dígito verificador correcto (calculado mod-11).
    assert cuil_valido("20-12345678-6") is True
    assert cuil_valido("20123456786") is True
    # Rama resto==11 → verificador 0 (prefijo 27).
    assert cuil_valido("27123456780") is True


def test_cuil_invalido_digito_verificador():
    assert cuil_valido("20-12345678-9") is False  # check debería ser 6, no 9
    assert cuil_valido("20123456780") is False


def test_cuil_invalido_formato():
    assert cuil_valido("123") is False
    assert cuil_valido(None) is False
    assert cuil_valido("abcdefghijk") is False
