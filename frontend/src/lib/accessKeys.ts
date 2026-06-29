/**
 * accessKeys.ts — "Métodos de acceso" del cliente: vista unificada de las llaves
 * de login (passkeys + identidades Google/mail) sobre `/cliente/auth/keys`.
 *
 * Agregar passkey vive en `lib/passkey` (registerPasskey); vincular Google es un
 * redirect a `/cliente/auth/google/link` (OAuth en link-mode). Acá: listar y quitar.
 */
import { authedJson } from "@/lib/authedFetch";

export type AccessKeyKind = "passkey" | "google" | "email";

export type AccessKey = {
  kind: AccessKeyKind;
  id: number;
  label: string;
  detail: string | null;
  created_at: string | null;
  last_used_at: string | null;
};

export async function listAccessKeys(): Promise<{ keys: AccessKey[]; total: number }> {
  return authedJson<{ keys: AccessKey[]; total: number }>("/cliente/auth/keys");
}

/** Quita una llave. El backend usa `passkey` para las passkeys e `identity` para
 * las identidades (Google/mail) — el caller mapea desde `AccessKey.kind`. */
export async function removeAccessKey(kind: "passkey" | "identity", id: number): Promise<void> {
  await authedJson(`/cliente/auth/keys/${kind}/${id}`, { method: "DELETE" });
}

/** Inicia el OAuth de Google en link-mode (vincular a la cuenta logueada). El
 * callback vuelve a /cliente/perfil?keys=<estado>. */
export const GOOGLE_LINK_URL = "/cliente/auth/google/link";
