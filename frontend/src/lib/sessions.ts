/**
 * sessions.ts — gestión de sesiones activas (revocación), sobre la cookie de sesión.
 *
 * Lista las sesiones vivas del dueño y permite cerrarlas server-side (logout real):
 * "cerrar mis otras sesiones" (todas salvo la actual) o una puntual. Scopeado por
 * `scope` (admin → /auth/sessions, cliente → /cliente/auth/sessions), espejando
 * `lib/passkey.ts`. La sesión la decide el backend (allowlist `auth_sessions`).
 */
import { authedJson, authedPostJson } from "@/lib/authedFetch";

export type SessionScope = "admin" | "cliente";

export type ActiveSession = {
  jti: string;
  user_agent: string | null;
  created_at: string | null;
  expires_at: string | null;
  current: boolean;
};

export type SessionsResponse = {
  sessions: ActiveSession[];
  current_jti: string | null;
};

const BASE: Record<SessionScope, string> = {
  admin: "/auth/sessions",
  cliente: "/cliente/auth/sessions",
};

export async function listSessions(scope: SessionScope): Promise<SessionsResponse> {
  return authedJson<SessionsResponse>(BASE[scope]);
}

/** Cierra todas las OTRAS sesiones del dueño (mantiene la actual). Devuelve cuántas cerró. */
export async function revokeOtherSessions(scope: SessionScope): Promise<number> {
  const data = await authedPostJson<{ ok: boolean; revoked: number }>(
    `${BASE[scope]}/revoke-all`,
    {},
  );
  return data.revoked;
}

/** Cierra una sesión puntual por su `jti` (el backend la scopea al dueño). */
export async function revokeSession(scope: SessionScope, jti: string): Promise<void> {
  await authedJson(`${BASE[scope]}/${encodeURIComponent(jti)}`, { method: "DELETE" });
}
