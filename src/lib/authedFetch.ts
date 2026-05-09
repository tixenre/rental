/**
 * authedFetch — wrapper de fetch que adjunta el JWT de Supabase Auth
 * cuando el usuario está logueado. El backend FastAPI valida ese JWT en
 * su middleware (ver `backend/supabase_auth.py`) y resuelve el cliente
 * por `supabase_uid`.
 *
 * Para endpoints públicos (catálogo, disponibilidad) el header es ignorado;
 * para endpoints privados el backend devuelve 401 si no hay token válido.
 */

import { supabase } from "@/integrations/supabase/client";

const API_BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

export type AuthedFetchInit = Omit<RequestInit, "headers"> & {
  headers?: Record<string, string>;
  /** Si true, NO incluye el Authorization header aunque haya sesión. */
  skipAuth?: boolean;
};

export async function authedFetch(path: string, init: AuthedFetchInit = {}): Promise<Response> {
  const { skipAuth, headers = {}, ...rest } = init;

  if (!skipAuth) {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
  return fetch(url, { ...rest, headers });
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
