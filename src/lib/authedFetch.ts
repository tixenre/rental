/**
 * authedFetch — wrapper de fetch que envía la cookie `session` del backend.
 */

// En dev el proxy de Vite reenvía /api y /auth a localhost:8000, así que
// usamos ruta relativa (API_BASE vacío). En prod VITE_API_URL apunta al dominio.
const API_BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

export type AuthedFetchInit = Omit<RequestInit, "headers"> & {
  headers?: Record<string, string>;
};

export async function authedFetch(path: string, init: AuthedFetchInit = {}): Promise<Response> {
  const { headers = {}, ...rest } = init;
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
  return fetch(url, { ...rest, headers, credentials: "include" });
}

export async function authedJson<T>(path: string, init: AuthedFetchInit = {}): Promise<T> {
  const res = await authedFetch(path, {
    ...init,
    headers: { Accept: "application/json", ...(init.headers ?? {}) },
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail?.detail ?? `${init.method ?? "GET"} ${path} → ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function authedPostJson<T>(
  path: string,
  body: unknown,
  init: AuthedFetchInit = {},
): Promise<T> {
  return authedJson<T>(path, {
    ...init,
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
    body: JSON.stringify(body),
  });
}
