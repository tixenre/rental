"""Tests de services.facturacion.diagnostico — sin red, sin Postgres real.

Cubre las dos capas del "middleman": local (siempre corre) + AFIP (solo si el
certificado pasa la capa local) — con foco en que el corte temprano de verdad
evita las llamadas a AFIP, no solo que el resultado final sea correcto."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services.facturacion import diagnostico

pytestmark = pytest.mark.unit


class _FakeEmisor:
    def __init__(
        self, *, activo=True, cuit="20301234563", cert_cargado=True, pto_vta=3, nombre="pablo",
    ):
        self.id = 1
        self.nombre = nombre
        self.activo = activo
        self.cuit = cuit
        self.cert_cargado = cert_cargado
        self.pto_vta = pto_vta


def _patch_emisor(monkeypatch, emisor, cert_pem=b"fake-cert"):
    monkeypatch.setattr(
        "services.facturacion.emisores_repo.get_by_id", lambda emisor_id, conn: emisor
    )
    monkeypatch.setattr(
        "services.facturacion.emisores_repo.get_cert_pem",
        lambda emisor_id, conn: (cert_pem, b"fake-key"),
    )


def _patch_cert_info(monkeypatch, *, vencido=False):
    vigente_hasta = (
        datetime.now(timezone.utc) - timedelta(days=1)
        if vencido
        else datetime.now(timezone.utc) + timedelta(days=365)
    )
    monkeypatch.setattr(
        diagnostico,
        "cert_info",
        lambda cert_pem: {
            "subject": "CN=test",
            "numero_serie": "1",
            "vigente_desde": datetime.now(timezone.utc) - timedelta(days=30),
            "vigente_hasta": vigente_hasta,
        },
    )


def _patch_afip_ok(monkeypatch, *, pto_vta_habilitado=True):
    monkeypatch.setattr(
        "services.facturacion.puntos_venta.consultar_puntos_venta",
        lambda nombre, conn: {
            "habilitados": [{"nro": 3}] if pto_vta_habilitado else [],
            "excluidos": [] if pto_vta_habilitado else [{"nro": 3, "motivo": "bloqueado"}],
        },
    )
    monkeypatch.setattr(
        "services.facturacion.config.credenciales",
        lambda nombre, conn: type("C", (), {"ambiente": "homologacion", "cuit": 20301234563})(),
    )
    monkeypatch.setattr(
        "services.facturacion.wsaa_cache.get_ta",
        lambda nombre, conn, servicio="wsfe": ("tok", "sign"),
    )
    monkeypatch.setattr(
        "arca_fe.padron.PadronClient.get_persona",
        lambda self, cuit: object(),
    )


def test_emisor_no_encontrado_levanta_value_error(monkeypatch):
    monkeypatch.setattr(
        "services.facturacion.emisores_repo.get_by_id", lambda emisor_id, conn: None
    )
    with pytest.raises(ValueError, match="no encontrado"):
        diagnostico.diagnosticar_emisor(1, conn=object())


def test_sin_certificado_corta_temprano_y_no_llama_a_afip(monkeypatch):
    _patch_emisor(monkeypatch, _FakeEmisor(cert_cargado=False))
    llamado = []
    monkeypatch.setattr(
        "services.facturacion.puntos_venta.consultar_puntos_venta",
        lambda *a, **kw: llamado.append(1),
    )
    monkeypatch.setattr(
        "services.facturacion.wsaa_cache.get_ta",
        lambda *a, **kw: llamado.append(1),
    )

    result = diagnostico.diagnosticar_emisor(1, conn=object())

    assert not llamado, "no debe llamar a AFIP si no hay certificado"
    assert result["listo"] is False
    afip_check = next(c for c in result["chequeos"] if c["check"] == "afip_no_verificado")
    assert "certificado" in afip_check["mensaje"]


def test_certificado_vencido_corta_temprano_y_no_llama_a_afip(monkeypatch):
    _patch_emisor(monkeypatch, _FakeEmisor(cert_cargado=True))
    _patch_cert_info(monkeypatch, vencido=True)
    llamado = []
    monkeypatch.setattr(
        "services.facturacion.puntos_venta.consultar_puntos_venta",
        lambda *a, **kw: llamado.append(1),
    )

    result = diagnostico.diagnosticar_emisor(1, conn=object())

    assert not llamado, "no debe llamar a AFIP si el certificado está vencido"
    assert result["listo"] is False
    cert_check = next(c for c in result["chequeos"] if c["check"] == "cert_vigente")
    assert cert_check["ok"] is False


def test_emisor_inactivo_corta_temprano_sin_rotular_como_falla_de_afip(monkeypatch):
    _patch_emisor(monkeypatch, _FakeEmisor(activo=False))
    _patch_cert_info(monkeypatch, vencido=False)
    llamado = []
    monkeypatch.setattr(
        "services.facturacion.puntos_venta.consultar_puntos_venta",
        lambda *a, **kw: llamado.append(1),
    )

    result = diagnostico.diagnosticar_emisor(1, conn=object())

    assert not llamado
    afip_check = next(c for c in result["chequeos"] if c["check"] == "afip_no_verificado")
    assert "desactivado" in afip_check["mensaje"]


def test_cuit_invalido_bloquea_sin_llamar_a_afip(monkeypatch):
    """Un CUIT con dígito verificador mal formado bloquea desde la capa local — pero
    NO corta el resto de los chequeos (fail-not-fast, mismo criterio que en toda la
    iniciativa): si el cert está OK, igual se intenta contra AFIP."""
    _patch_emisor(monkeypatch, _FakeEmisor(cuit="20301234560"))  # dígito verificador incorrecto
    _patch_cert_info(monkeypatch, vencido=False)
    _patch_afip_ok(monkeypatch)

    result = diagnostico.diagnosticar_emisor(1, conn=object())

    cuit_check = next(c for c in result["chequeos"] if c["check"] == "cuit_valido")
    assert cuit_check["ok"] is False
    assert result["listo"] is False


def test_todo_ok_da_listo_true(monkeypatch):
    _patch_emisor(monkeypatch, _FakeEmisor())
    _patch_cert_info(monkeypatch, vencido=False)
    _patch_afip_ok(monkeypatch, pto_vta_habilitado=True)

    result = diagnostico.diagnosticar_emisor(1, conn=object())

    assert result["listo"] is True
    for check in ("cuit_valido", "cert_cargado", "cert_vigente", "punto_venta_asignado",
                  "wsfe_habilitado", "punto_venta_habilitado", "padron_habilitado"):
        c = next(c for c in result["chequeos"] if c["check"] == check)
        assert c["ok"] is True, f"{check} debería estar ok"


def test_consultar_puntos_venta_falla_bloquea_y_saltea_punto_venta_habilitado(monkeypatch):
    _patch_emisor(monkeypatch, _FakeEmisor())
    _patch_cert_info(monkeypatch, vencido=False)

    def _boom(nombre, conn):
        raise RuntimeError("ARCA no respondió")

    monkeypatch.setattr("services.facturacion.puntos_venta.consultar_puntos_venta", _boom)
    monkeypatch.setattr(
        "services.facturacion.config.credenciales",
        lambda nombre, conn: type("C", (), {"ambiente": "homologacion", "cuit": 20301234563})(),
    )
    monkeypatch.setattr(
        "services.facturacion.wsaa_cache.get_ta",
        lambda nombre, conn, servicio="wsfe": ("tok", "sign"),
    )
    monkeypatch.setattr("arca_fe.padron.PadronClient.get_persona", lambda self, cuit: object())

    result = diagnostico.diagnosticar_emisor(1, conn=object())

    checks = {c["check"]: c for c in result["chequeos"]}
    assert checks["wsfe_habilitado"]["ok"] is False
    assert checks["wsfe_habilitado"]["bloqueante"] is True
    assert "punto_venta_habilitado" not in checks
    assert result["listo"] is False


def test_punto_venta_excluido_muestra_el_motivo_real(monkeypatch):
    _patch_emisor(monkeypatch, _FakeEmisor())
    _patch_cert_info(monkeypatch, vencido=False)
    _patch_afip_ok(monkeypatch, pto_vta_habilitado=False)

    result = diagnostico.diagnosticar_emisor(1, conn=object())

    check = next(c for c in result["chequeos"] if c["check"] == "punto_venta_habilitado")
    assert check["ok"] is False
    assert "bloqueado" in check["mensaje"]


def test_padron_falla_no_bloquea_el_listo(monkeypatch):
    """El padrón nunca es crítico para facturar — si falla, se informa pero
    NO impide que `listo=True` si el resto de los chequeos está bien."""
    _patch_emisor(monkeypatch, _FakeEmisor())
    _patch_cert_info(monkeypatch, vencido=False)
    _patch_afip_ok(monkeypatch, pto_vta_habilitado=True)

    def _boom(self, cuit):
        raise RuntimeError("relación no delegada")

    monkeypatch.setattr("arca_fe.padron.PadronClient.get_persona", _boom)

    result = diagnostico.diagnosticar_emisor(1, conn=object())

    check = next(c for c in result["chequeos"] if c["check"] == "padron_habilitado")
    assert check["ok"] is False
    assert check["bloqueante"] is False
    assert result["listo"] is True, "padrón no crítico no debe bloquear listo"
