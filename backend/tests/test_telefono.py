"""Tests del embudo único de teléfonos (services/telefono) — puro, sin DB/red."""
from __future__ import annotations

from services.telefono import es_valido, formatear_para_guardar, normalizar_e164


def test_normaliza_movil_ar_con_prefijo_15():
    # libphonenumber entiende el 0/15 local argentino.
    assert normalizar_e164("011 15 1234 5678") == "+5491112345678"


def test_normaliza_local_a_e164():
    assert normalizar_e164("223 555-0100") == "+542235550100"
    assert normalizar_e164("1122334455") == "+541122334455"


def test_ya_e164_se_mantiene():
    assert normalizar_e164("+5492235551234") == "+5492235551234"
    assert normalizar_e164("+54 9 223 555 0100") == "+5492235550100"


def test_invalido_o_vacio_da_none():
    for malo in ("1111-0000", "222-nuevo", "", "   ", None):
        assert normalizar_e164(malo) is None


def test_formatear_para_guardar_valido_es_e164():
    assert formatear_para_guardar("011 15 1234 5678") == "+5491112345678"
    assert formatear_para_guardar("+5492235551234") == "+5492235551234"


def test_formatear_para_guardar_invalido_conserva_crudo():
    # Lenient: no se pierde el dato ni se bloquea el guardado (el rechazo duro es UX aparte).
    assert formatear_para_guardar("1111-0000") == "1111-0000"
    assert formatear_para_guardar("  222-nuevo ") == "222-nuevo"


def test_formatear_para_guardar_vacio_es_none():
    for vacio in ("", "   ", None):
        assert formatear_para_guardar(vacio) is None


def test_es_valido():
    assert es_valido("+5492235551234") is True
    assert es_valido("1111-0000") is False
