"""Tests de `/auth/staging-verify` — fakear la verificación de identidad Didit en dev.

Didit (KYC) no corre en dev/staging, así que una cuenta nunca llega a
`dni_validado_at` por el flujo real y el portero del checkout la bloquea. Este
endpoint fakea la verificación REUSANDO la pluma única `identity.kyc`. El gate es
el mismo crítico que `/auth/staging-login`: NUNCA en prod, solo con secreto.

Unitarios sin DB: se mockea `_aplicar_verificacion_fake` (el único que toca la DB)
y `_resolve_staging_cliente`. El CUIL fake se testea puro contra `anchor.cuil_valido`.
"""
import pytest
from fastapi import HTTPException

import config
import auth.staging as auth
from auth.ratelimit import _failures as _rl_failures
from identity.anchor import cuil_valido

pytestmark = pytest.mark.unit


class _FakeHeaders:
    def get(self, _key, default=""):
        return default


class _FakeRequest:
    def __init__(self, host="203.0.113.9"):
        self.headers = _FakeHeaders()
        self.client = type("C", (), {"host": host})()
        self.cookies = {}


def _env(monkeypatch, railway_env, secret=None):
    monkeypatch.setattr(config.settings, "RAILWAY_ENVIRONMENT", railway_env)
    if secret is None:
        monkeypatch.delenv("STAGING_LOGIN_SECRET", raising=False)
    else:
        monkeypatch.setenv("STAGING_LOGIN_SECRET", secret)
    _rl_failures.clear()


@pytest.fixture(autouse=True)
def _stub_db_layer(monkeypatch):
    """Aísla los tests del endpoint de la DB: el resolver da un cliente fijo y la
    aplicación de la verificación se mockea (se prueba el ruteo/gate, no la DB)."""
    monkeypatch.setattr(
        auth, "_resolve_staging_cliente",
        lambda cid: {"id": cid or 209, "email": "cli@rambla.local", "name": "Tincho Test"},
    )
    monkeypatch.setattr(auth, "_aplicar_verificacion_fake", lambda *a, **k: True)


# ── Gate de doble llave (heredado de staging-login) ──────────────────────────

class TestGate:
    def test_404_si_no_habilitado(self, monkeypatch):
        _env(monkeypatch, "dev", None)  # sin secreto → como si no existiera
        with pytest.raises(HTTPException) as exc:
            auth.auth_staging_verify(auth.StagingVerifyInput(secret="x"), _FakeRequest())
        assert exc.value.status_code == 404

    def test_404_en_prod_aunque_secreto_correcto(self, monkeypatch):
        _env(monkeypatch, "production", "s3cr3t")
        with pytest.raises(HTTPException) as exc:
            auth.auth_staging_verify(auth.StagingVerifyInput(secret="s3cr3t"), _FakeRequest())
        assert exc.value.status_code == 404

    def test_401_secreto_incorrecto(self, monkeypatch):
        _env(monkeypatch, "dev", "s3cr3t")
        with pytest.raises(HTTPException) as exc:
            auth.auth_staging_verify(auth.StagingVerifyInput(secret="wrong"), _FakeRequest())
        assert exc.value.status_code == 401


# ── Comportamiento ───────────────────────────────────────────────────────────

class TestEndpoint:
    def test_approved_default_verifica_al_cliente(self, monkeypatch):
        _env(monkeypatch, "dev", "s3cr3t")
        capturado = {}
        monkeypatch.setattr(
            auth, "_aplicar_verificacion_fake",
            lambda cid, name, email, estado: capturado.update(
                cid=cid, name=name, email=email, estado=estado) or True,
        )
        res = auth.auth_staging_verify(
            auth.StagingVerifyInput(secret="s3cr3t", cliente_id=209), _FakeRequest()
        )
        assert res == {"ok": True, "cliente_id": 209, "estado": "approved"}
        assert capturado["estado"] == "approved"
        assert capturado["cid"] == 209
        assert capturado["email"] == "cli@rambla.local"  # del cliente resuelto

    def test_estado_invalido_400(self, monkeypatch):
        _env(monkeypatch, "dev", "s3cr3t")
        with pytest.raises(HTTPException) as exc:
            auth.auth_staging_verify(
                auth.StagingVerifyInput(secret="s3cr3t", estado="aprobadísimo"), _FakeRequest()
            )
        assert exc.value.status_code == 400

    def test_estado_rejected_se_pasa(self, monkeypatch):
        _env(monkeypatch, "dev", "s3cr3t")
        capturado = {}
        monkeypatch.setattr(
            auth, "_aplicar_verificacion_fake",
            lambda cid, name, email, estado: capturado.update(estado=estado) or True,
        )
        auth.auth_staging_verify(
            auth.StagingVerifyInput(secret="s3cr3t", estado="rejected"), _FakeRequest()
        )
        assert capturado["estado"] == "rejected"

    def test_404_si_cliente_no_existe(self, monkeypatch):
        _env(monkeypatch, "dev", "s3cr3t")
        monkeypatch.setattr(auth, "_resolve_staging_cliente", lambda cid: None)
        with pytest.raises(HTTPException) as exc:
            auth.auth_staging_verify(auth.StagingVerifyInput(secret="s3cr3t"), _FakeRequest())
        assert exc.value.status_code == 404

    def test_email_override_se_respeta(self, monkeypatch):
        """Para una cuenta liviana sin email base, el body puede sembrar el contacto."""
        _env(monkeypatch, "dev", "s3cr3t")
        capturado = {}
        monkeypatch.setattr(
            auth, "_resolve_staging_cliente",
            lambda cid: {"id": 7, "email": None, "name": "Liviana"},
        )
        monkeypatch.setattr(
            auth, "_aplicar_verificacion_fake",
            lambda cid, name, email, estado: capturado.update(email=email) or True,
        )
        auth.auth_staging_verify(
            auth.StagingVerifyInput(secret="s3cr3t", cliente_id=7, email="yo@test.local"),
            _FakeRequest(),
        )
        assert capturado["email"] == "yo@test.local"

    def test_email_fallback_derivado_si_no_hay(self, monkeypatch):
        """Sin email base ni override → uno derivado (la cuenta igual queda con contacto)."""
        _env(monkeypatch, "dev", "s3cr3t")
        capturado = {}
        monkeypatch.setattr(
            auth, "_resolve_staging_cliente",
            lambda cid: {"id": 7, "email": None, "name": "Liviana"},
        )
        monkeypatch.setattr(
            auth, "_aplicar_verificacion_fake",
            lambda cid, name, email, estado: capturado.update(email=email) or True,
        )
        auth.auth_staging_verify(
            auth.StagingVerifyInput(secret="s3cr3t", cliente_id=7), _FakeRequest()
        )
        assert capturado["email"] == "verificado-7@rambla.local"


# ── El CUIL fake es válido (mod-11) y único ──────────────────────────────────

class TestCuilFake:
    def test_cuil_fake_pasa_la_validacion(self):
        for cid in (1, 7, 209, 1000, 8_999_999, 9_000_001):
            assert cuil_valido(auth._cuil_fake(cid)), f"CUIL inválido para id={cid}"

    def test_cuil_fake_unico_por_cliente(self):
        ids = [1, 2, 3, 209, 500]
        cuils = [auth._cuil_fake(c) for c in ids]
        assert len(set(cuils)) == len(cuils)

    def test_cuil_fake_tiene_11_digitos(self):
        c = auth._cuil_fake(209)
        assert len(c) == 11 and c.isdigit() and c.startswith("20")
