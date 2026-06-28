/**
 * passkey.ts — cliente WebAuthn (login con passkey), aditivo a Google OAuth.
 *
 * Envuelve `@simplewebauthn/browser` + los endpoints de `routes/auth_passkey`.
 * El login es **discoverable** (un solo endpoint resuelve admin y cliente); el
 * registro y la gestión van scopeados (`admin` → /auth/passkey, `cliente` →
 * /cliente/auth/passkey). La sesión la mintea el backend (misma cookie que OAuth).
 */
import {
  WebAuthnError,
  browserSupportsWebAuthn,
  startAuthentication,
  startRegistration,
} from "@simplewebauthn/browser";
import type {
  PublicKeyCredentialCreationOptionsJSON,
  PublicKeyCredentialRequestOptionsJSON,
} from "@simplewebauthn/browser";

import { AuthedHttpError, authedJson, authedPostJson } from "@/lib/authedFetch";

export type PasskeyScope = "admin" | "cliente";

export type PasskeyCredential = {
  id: number;
  device_name: string | null;
  transports: string | null;
  created_at: string | null;
  last_used_at: string | null;
};

const BASE: Record<PasskeyScope, string> = {
  admin: "/auth/passkey",
  cliente: "/cliente/auth/passkey",
};

export function passkeySupported(): boolean {
  return browserSupportsWebAuthn();
}

function defaultDeviceName(): string {
  const ua = typeof navigator !== "undefined" ? navigator.userAgent : "";
  if (/iPhone|iPad|iPod/.test(ua)) return "iPhone/iPad";
  if (/Macintosh/.test(ua)) return "Mac";
  if (/Android/.test(ua)) return "Android";
  if (/CrOS/.test(ua)) return "Chromebook";
  if (/Windows/.test(ua)) return "Windows";
  if (/Linux/.test(ua)) return "Linux";
  return "Passkey";
}

/** Registra una passkey nueva (usuario ya logueado por Google). */
export async function registerPasskey(scope: PasskeyScope, deviceName?: string): Promise<void> {
  const optionsJSON = await authedPostJson<PublicKeyCredentialCreationOptionsJSON>(
    `${BASE[scope]}/register/begin`,
    {},
  );
  const credential = await startRegistration({ optionsJSON });
  await authedPostJson(`${BASE[scope]}/register/complete`, {
    credential,
    device_name: deviceName ?? defaultDeviceName(),
  });
}

/** Entra con una passkey (discoverable: el browser ofrece las disponibles). */
export async function loginWithPasskey(): Promise<void> {
  const optionsJSON = await authedPostJson<PublicKeyCredentialRequestOptionsJSON>(
    "/auth/passkey/login/begin",
    {},
  );
  const credential = await startAuthentication({ optionsJSON });
  await authedPostJson("/auth/passkey/login/complete", { credential });
}

export async function listPasskeys(scope: PasskeyScope): Promise<PasskeyCredential[]> {
  const data = await authedJson<{ credentials: PasskeyCredential[] }>(`${BASE[scope]}/credentials`);
  return data.credentials;
}

export async function deletePasskey(scope: PasskeyScope, id: number): Promise<void> {
  await authedJson(`${BASE[scope]}/credentials/${id}`, { method: "DELETE" });
}

export async function renamePasskey(
  scope: PasskeyScope,
  id: number,
  deviceName: string,
): Promise<void> {
  await authedJson(`${BASE[scope]}/credentials/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ device_name: deviceName }),
  });
}

/** Mensaje en español para los errores típicos de WebAuthn + del backend. */
export function passkeyErrorMessage(e: unknown): string {
  if (!passkeySupported()) return "Tu navegador no soporta passkeys.";
  if (e instanceof WebAuthnError) {
    if (e.code === "ERROR_CEREMONY_ABORTED") return "Cancelaste la operación. Probá de nuevo.";
    if (e.code === "ERROR_AUTHENTICATOR_PREVIOUSLY_REGISTERED")
      return "Esa passkey ya está registrada.";
    if (e.code === "ERROR_AUTHENTICATOR_MISSING_DISCOVERABLE_CREDENTIAL_SUPPORT")
      return "Tu dispositivo no puede crear passkeys.";
    return "No se pudo completar la operación con la passkey.";
  }
  if (e instanceof AuthedHttpError) return e.message;
  if (e instanceof Error && e.message) return e.message;
  return "No se pudo completar la operación con la passkey.";
}
