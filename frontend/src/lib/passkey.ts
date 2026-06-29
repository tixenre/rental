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
  return "Clave de acceso";
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

/** Crea una cuenta NUEVA con una passkey (alta passwordless, estilo Vercel): el
 * usuario deslogueado registra una passkey y el backend le mintea una cuenta-cliente
 * liviana + la sesión, sin tipear nada. La identidad la completa Didit al primer
 * pedido. Discoverable → la passkey queda descubrible para entrar después. */
export async function signupWithPasskey(deviceName?: string): Promise<void> {
  const optionsJSON = await authedPostJson<PublicKeyCredentialCreationOptionsJSON>(
    "/auth/passkey/signup/begin",
    {},
  );
  const credential = await startRegistration({ optionsJSON });
  await authedPostJson("/auth/passkey/signup/complete", {
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

/** Step-up: confirmá que sos vos con una passkey antes de una acción sensible (quitar
 * una llave; futuro: confirmar un pedido). NO loguea — deja una marca de corta vida que
 * el backend exige (`require_recent_auth`). Discoverable: el browser ofrece tus passkeys. */
export async function stepUpWithPasskey(): Promise<void> {
  const optionsJSON = await authedPostJson<PublicKeyCredentialRequestOptionsJSON>(
    "/cliente/auth/passkey/stepup/begin",
    {},
  );
  const credential = await startAuthentication({ optionsJSON });
  await authedPostJson("/cliente/auth/passkey/stepup/complete", { credential });
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
  if (!passkeySupported()) return "Tu navegador no soporta claves de acceso.";
  if (e instanceof WebAuthnError) {
    if (e.code === "ERROR_CEREMONY_ABORTED") return "Cancelaste la operación. Probá de nuevo.";
    if (e.code === "ERROR_AUTHENTICATOR_PREVIOUSLY_REGISTERED")
      return "Esa clave de acceso ya está registrada.";
    if (e.code === "ERROR_AUTHENTICATOR_MISSING_DISCOVERABLE_CREDENTIAL_SUPPORT")
      return "Tu dispositivo no puede crear claves de acceso.";
    return "No se pudo completar la operación con la clave de acceso.";
  }
  if (e instanceof AuthedHttpError) return e.message;
  if (e instanceof Error && e.message) return e.message;
  return "No se pudo completar la operación con la clave de acceso.";
}

/** Mensaje para fallos del LOGIN con passkey. El browser NO distingue "cancelaste"
 * de "no hay passkey en este dispositivo" (ambos → ERROR_CEREMONY_ABORTED), y la
 * causa #1 de un login fallido es no tener una passkey registrada todavía → guiamos
 * a crear una (Google + perfil) en vez del genérico "Cancelaste". */
export function passkeyLoginErrorMessage(e: unknown): string {
  if (e instanceof WebAuthnError && e.code === "ERROR_CEREMONY_ABORTED") {
    return "No encontramos una clave de acceso en este dispositivo (o cancelaste). Si es tu primera vez, entrá con Google y agregá una clave de acceso desde tu perfil.";
  }
  return passkeyErrorMessage(e);
}
