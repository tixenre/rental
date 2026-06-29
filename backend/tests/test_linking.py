"""Tests de account-linking: API unificada de llaves (auth/linking) + helpers del
linking de Google (auth/google). DB mockeada — se prueba la lógica nuestra: unión
de passkeys + identidades, guardrail de "última llave", scoping anti-IDOR, y que un
link a una cuenta ajena se rechaza.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth.session import signer
from auth import auth_linking_router
from auth import identities_store
from auth.passkey import store as passkey_store

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _stub_sessions_store(monkeypatch):
    # get_session valida la firma Y que el jti siga vivo (allowlist) → lo damos por activo.
    monkeypatch.setattr("auth.sessions_store.is_active", lambda jti: {"jti": jti} if jti else None)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(auth_linking_router)
    return TestClient(app)


def _cliente_session(cliente_id: int = 42) -> str:
    return signer.dumps(
        {"email": "c@x.com", "name": "Cli", "role": "cliente", "cliente_id": cliente_id, "jti": "t"}
    )


class TestListKeys:
    def test_sin_sesion_401(self):
        assert _client().get("/cliente/auth/keys").status_code == 401

    def test_une_passkeys_e_identidades(self, monkeypatch):
        monkeypatch.setattr(passkey_store, "list_for_owner", lambda *a, **k: [
            {"id": 1, "device_name": "iPhone", "transports": "internal",
             "created_at": "2026-01-01", "last_used_at": None}])
        monkeypatch.setattr(identities_store, "list_for_cliente", lambda cid: [
            {"id": 5, "method": "google", "identifier": "sub-abc",
             "verified_at": "x", "created_at": "2026-01-02"}])
        c = _client()
        c.cookies.set("session", _cliente_session())
        r = c.get("/cliente/auth/keys")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 2
        by_kind = {k["kind"]: k for k in data["keys"]}
        assert by_kind["passkey"]["label"] == "iPhone"
        # Google muestra label genérico (el identifier es el `sub` opaco, no se expone).
        assert by_kind["google"]["label"] == "Google"
        assert "sub-abc" not in r.text


class TestRemoveKey:
    def _stub_counts(self, monkeypatch, *, passkeys: int, identities: int):
        monkeypatch.setattr(passkey_store, "list_for_owner",
                            lambda *a, **k: [{"id": i} for i in range(passkeys)])
        monkeypatch.setattr(identities_store, "count_for_cliente", lambda cid: identities)

    def test_guardrail_ultima_llave_409(self, monkeypatch):
        self._stub_counts(monkeypatch, passkeys=1, identities=0)  # total = 1
        c = _client()
        c.cookies.set("session", _cliente_session())
        r = c.delete("/cliente/auth/keys/passkey/1")
        assert r.status_code == 409

    def test_borra_passkey_scopeado_al_dueno(self, monkeypatch):
        self._stub_counts(monkeypatch, passkeys=2, identities=0)  # total = 2 → se puede
        captured = {}

        def fake_del(key_id, owner_type, *, owner_email=None, cliente_id=None):
            captured.update(key_id=key_id, owner_type=owner_type, cliente_id=cliente_id)
            return True

        monkeypatch.setattr(passkey_store, "delete_for_owner", fake_del)
        c = _client()
        c.cookies.set("session", _cliente_session(cliente_id=42))
        r = c.delete("/cliente/auth/keys/passkey/1")
        assert r.status_code == 200
        # pasa el cliente_id de la SESIÓN (42), no algo del request → anti-IDOR
        assert captured == {"key_id": 1, "owner_type": "cliente", "cliente_id": 42}

    def test_borra_identidad_scopeado_al_dueno(self, monkeypatch):
        self._stub_counts(monkeypatch, passkeys=1, identities=1)  # total = 2
        captured = {}
        monkeypatch.setattr(identities_store, "unlink_for_cliente",
                            lambda pk, cid: captured.update(pk=pk, cid=cid) or True)
        c = _client()
        c.cookies.set("session", _cliente_session(cliente_id=42))
        r = c.delete("/cliente/auth/keys/identity/5")
        assert r.status_code == 200
        assert captured == {"pk": 5, "cid": 42}

    def test_kind_invalido_404(self, monkeypatch):
        self._stub_counts(monkeypatch, passkeys=2, identities=0)
        c = _client()
        c.cookies.set("session", _cliente_session())
        assert c.delete("/cliente/auth/keys/banana/1").status_code == 404

    def test_no_encontrada_404(self, monkeypatch):
        self._stub_counts(monkeypatch, passkeys=2, identities=0)
        monkeypatch.setattr(passkey_store, "delete_for_owner", lambda *a, **k: False)
        c = _client()
        c.cookies.set("session", _cliente_session())
        assert c.delete("/cliente/auth/keys/passkey/99").status_code == 404


class TestGoogleLinkHelpers:
    def test_state_roundtrip_extrae_cliente_id(self):
        from auth.google import _link_cliente_id_de_state
        assert _link_cliente_id_de_state(signer.dumps({"nonce": "x", "link_cliente_id": 42})) == 42

    def test_state_de_login_normal_es_none(self):
        from auth.google import _link_cliente_id_de_state
        assert _link_cliente_id_de_state(signer.dumps({"nonce": "x"})) is None

    def test_state_tampered_es_none(self):
        from auth.google import _link_cliente_id_de_state
        assert _link_cliente_id_de_state("garbage") is None

    def test_completar_link_ok(self, monkeypatch):
        from auth import google
        monkeypatch.setattr(google, "get_session", lambda req: {"role": "cliente", "cliente_id": 42})
        monkeypatch.setattr("auth.identities_store.link_identity", lambda **kw: "linked")
        res = google._completar_link_google(None, 42, "sub-abc")
        assert res.status_code == 303 and "keys=ok" in res.headers["location"]

    def test_completar_link_taken_by_other_rutea_a_merge(self, monkeypatch):
        # taken_by_other ya NO es un dead-end: rutea al intento de merge (misma persona).
        from auth import google
        monkeypatch.setattr(google, "get_session", lambda req: {"role": "cliente", "cliente_id": 42})
        monkeypatch.setattr("auth.identities_store.link_identity", lambda **kw: "taken_by_other")
        calls = {}
        monkeypatch.setattr(google, "_merge_cuentas_por_google",
                            lambda req, *, actual, sub: calls.update(actual=actual, sub=sub) or "MERGE")
        out = google._completar_link_google(None, 42, "sub-abc")
        assert out == "MERGE"
        assert calls == {"actual": 42, "sub": "sub-abc"}

    def test_completar_link_sesion_ajena_rechazado(self, monkeypatch):
        # El state dice cuenta 42 pero la sesión actual es la 99 → no se vincula (defensa).
        from auth import google
        called = {"n": 0}
        monkeypatch.setattr(google, "get_session", lambda req: {"role": "cliente", "cliente_id": 99})
        monkeypatch.setattr("auth.identities_store.link_identity",
                            lambda **kw: called.update(n=called["n"] + 1) or "linked")
        res = google._completar_link_google(None, 42, "sub-abc")
        assert "keys=error" in res.headers["location"]
        assert called["n"] == 0  # nunca llamó a link_identity


class TestMergePorGoogle:
    """El Google ya es de otra cuenta → se unen si una es absorbible (misma persona)."""

    def test_actual_absorbable_merge_y_entra_a_la_real(self, monkeypatch):
        from auth import google
        monkeypatch.setattr("auth.identities_store.find_cliente_by_identity", lambda m, i: 99)
        # actual (42, la liviana) es absorbible; otra (99, la real) no
        monkeypatch.setattr("auth.account_merge.account_is_absorbable", lambda cid: cid == 42)
        calls = {}
        monkeypatch.setattr("auth.account_merge.merge_accounts", lambda **kw: calls.update(merge=kw))
        monkeypatch.setattr(
            google, "_mint_session_para_cuenta",
            lambda cid, req, *, redirect: calls.update(mint=(cid, redirect)) or "MINTED")
        out = google._merge_cuentas_por_google(None, actual=42, sub="s")
        assert out == "MINTED"
        assert calls["merge"] == {"source": 42, "target": 99}  # absorbe la liviana en la real
        assert calls["mint"][0] == 99 and "keys=merged" in calls["mint"][1]

    def test_otra_absorbable_la_absorbe_y_se_queda(self, monkeypatch):
        from auth import google
        monkeypatch.setattr("auth.identities_store.find_cliente_by_identity", lambda m, i: 99)
        # otra (99) es la liviana; actual (42) es la real donde estás
        monkeypatch.setattr("auth.account_merge.account_is_absorbable", lambda cid: cid == 99)
        calls = {}
        monkeypatch.setattr("auth.account_merge.merge_accounts", lambda **kw: calls.update(merge=kw))
        out = google._merge_cuentas_por_google(None, actual=42, sub="s")
        assert calls["merge"] == {"source": 99, "target": 42}
        assert out.status_code == 303 and "keys=merged" in out.headers["location"]

    def test_ninguna_absorbable_no_mergea(self, monkeypatch):
        from auth import google
        monkeypatch.setattr("auth.identities_store.find_cliente_by_identity", lambda m, i: 99)
        monkeypatch.setattr("auth.account_merge.account_is_absorbable", lambda cid: False)
        called = {"n": 0}
        monkeypatch.setattr("auth.account_merge.merge_accounts",
                            lambda **kw: called.update(n=called["n"] + 1))
        out = google._merge_cuentas_por_google(None, actual=42, sub="s")
        assert "keys=taken" in out.headers["location"]
        assert called["n"] == 0  # ambas con datos → no toca nada (Fase 2)

    def test_google_ya_no_tomado_error(self, monkeypatch):
        from auth import google
        monkeypatch.setattr("auth.identities_store.find_cliente_by_identity", lambda m, i: None)
        out = google._merge_cuentas_por_google(None, actual=42, sub="s")
        assert "keys=error" in out.headers["location"]
