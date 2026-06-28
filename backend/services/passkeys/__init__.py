"""Motor único de passkeys (WebAuthn/FIDO2) — aditivo a Google OAuth.

Aísla la integración WebAuthn del transporte HTTP (`routes/auth_passkey.py`),
como `services/didit/` aísla la verificación de identidad. Tres piezas:

- `config`     → `rp_id` / origins derivados por ambiente (fuente única).
- `ceremonies` → armado de opciones + verificación + firma del challenge.
- `store`      → persistencia (tabla `passkey_credentials`), escrituras scopeadas
                 al dueño (anti-IDOR).

La sesión que se mintea al loguear con passkey es la **misma** cookie firmada que
el OAuth (`routes/auth._make_session_response`) — la passkey es un método de
login más, no una sesión paralela.
"""
