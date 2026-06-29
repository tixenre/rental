"""Ceremonias WebAuthn (registro + autenticación) — lógica sobre py_webauthn.

No toca HTTP ni cookies (eso es transporte, en `routes/auth_passkey.py`): acá
viven el armado de opciones, la verificación de la respuesta del autenticador, y
la firma del **challenge**. El challenge se guarda firmado con `itsdangerous`
(mismo `SECRET_KEY`, salt propio) en una cookie de corta vida — sin infra extra
(ni Redis ni tabla), espejando cómo `routes/auth.py` firma el `oauth_state`.
"""
import hashlib
import json

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from config import settings
from auth.passkey import config as rpcfg

# El challenge vive ~5 min: suficiente para completar la ceremonia, corto para
# limitar el reuso. La firma + max_age los hace cumplir itsdangerous.
CHALLENGE_MAX_AGE = 300

_challenge_signer = URLSafeTimedSerializer(settings.SECRET_KEY, salt="passkey-challenge")


def user_handle_for(owner_type: str, owner_key: str) -> str:
    """Handle opaco y **estable por dueño** (base64url de sha256). No expone el
    email/id crudos al autenticador (que lo persiste para passkeys discoverable)."""
    digest = hashlib.sha256(f"{owner_type}:{owner_key}".encode()).digest()
    return bytes_to_base64url(digest)


# ── Challenge firmado (cookie) ───────────────────────────────────────────────

def sign_challenge(challenge_b64: str, **bind) -> str:
    """Firma el challenge (+ binding opcional del dueño para el registro)."""
    return _challenge_signer.dumps({"challenge": challenge_b64, **bind})


def read_challenge(token: str) -> dict | None:
    """Devuelve el payload del challenge si la firma es válida y no expiró."""
    try:
        return _challenge_signer.loads(token, max_age=CHALLENGE_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


# ── Registro ─────────────────────────────────────────────────────────────────

def build_registration_options(
    *, user_name: str, user_display_name: str, user_handle_b64: str, exclude_ids: list[str]
) -> tuple[dict, str]:
    """(options_json, challenge_b64) para `navigator.credentials.create`."""
    exclude = [PublicKeyCredentialDescriptor(id=base64url_to_bytes(cid)) for cid in exclude_ids]
    options = generate_registration_options(
        rp_id=rpcfg.rp_id(),
        rp_name=rpcfg.RP_NAME,
        user_name=user_name,
        user_id=base64url_to_bytes(user_handle_b64),
        user_display_name=user_display_name,
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        exclude_credentials=exclude or None,
    )
    return json.loads(options_to_json(options)), bytes_to_base64url(options.challenge)


def verify_registration(*, credential, challenge_b64: str) -> dict:
    """Verifica la respuesta de registro. Lanza si es inválida. Devuelve los
    campos a persistir (credential_id / public_key en base64url, sign_count, aaguid)."""
    v = verify_registration_response(
        credential=credential,
        expected_challenge=base64url_to_bytes(challenge_b64),
        expected_rp_id=rpcfg.rp_id(),
        expected_origin=rpcfg.expected_origins(),
        require_user_verification=False,
    )
    return {
        "credential_id": bytes_to_base64url(v.credential_id),
        "public_key": bytes_to_base64url(v.credential_public_key),
        "sign_count": v.sign_count,
        "aaguid": v.aaguid,
    }


# ── Autenticación (login) ────────────────────────────────────────────────────

def build_authentication_options() -> tuple[dict, str]:
    """(options_json, challenge_b64) para `navigator.credentials.get`. Sin
    `allowCredentials` → login **discoverable** (usernameless): el browser ofrece
    las passkeys disponibles y el lookup en el server es por credential_id."""
    options = generate_authentication_options(
        rp_id=rpcfg.rp_id(),
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    return json.loads(options_to_json(options)), bytes_to_base64url(options.challenge)


def verify_authentication(*, credential, challenge_b64: str, public_key_b64: str, current_sign_count: int) -> int:
    """Verifica la assertion. Lanza si es inválida. Devuelve el nuevo sign_count."""
    v = verify_authentication_response(
        credential=credential,
        expected_challenge=base64url_to_bytes(challenge_b64),
        expected_rp_id=rpcfg.rp_id(),
        expected_origin=rpcfg.expected_origins(),
        credential_public_key=base64url_to_bytes(public_key_b64),
        credential_current_sign_count=current_sign_count,
        require_user_verification=False,
    )
    return v.new_sign_count


def es_replay(stored: int, new: int) -> bool:
    """Clonación/replay: el contador del autenticador no avanzó. **Excepción:**
    `0/0` = passkey sincronizada (iCloud/Google) que no lleva contador → NO es
    replay (rechazarla bloquearía a usuarios legítimos)."""
    if stored == 0 and new == 0:
        return False
    return new <= stored
