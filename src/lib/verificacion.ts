import { useEffect } from "react";
import { toast } from "sonner";
import { authedFetch } from "./authedFetch";

export type EstadoCuenta = "no-logueado" | "no-verificado" | "logueado-verificado" | "error";

/** Lee /api/cliente/me (que ya devuelve dni_validado_at) y clasifica la cuenta.
 *  Fuente única del pre-check de checkout (reemplaza el `me.ok` suelto de las bocas). */
export async function chequearEstadoCuenta(): Promise<EstadoCuenta> {
  try {
    const r = await authedFetch("/api/cliente/me");
    if (!r.ok) return r.status === 401 ? "no-logueado" : "error";
    const me = await r.json();
    return me?.dni_validado_at ? "logueado-verificado" : "no-verificado";
  } catch {
    return "error";
  }
}

/** Allowlist anti open-redirect — ESPEJO del backend `_es_path_interno_seguro` (didit.py).
 *  Si tocás uno, tocá el otro. */
export function esPathInternoSeguro(p: string | null | undefined): boolean {
  if (!p || typeof p !== "string") return false;
  if (p.length > 512) return false;
  if (!p.startsWith("/") || p.startsWith("//")) return false;
  if (p.includes("://") || p.includes("\\")) return false;
  // Rechazo explícito de caracteres de control (0x00-0x1F y 0x7F) en el path,
  // por charCode para no necesitar un regex con control chars (lint-safe).
  for (let i = 0; i < p.length; i++) {
    const c = p.charCodeAt(i);
    if (c <= 0x1f || c === 0x7f) return false;
  }
  return true;
}

/** Dispara la sesión Didit y redirige (full-nav). `returnTo`: path interno a donde
 *  volver tras verificar. En error muestra toast y re-tira (para que el caller resetee loading). */
export async function iniciarVerificacionIdentidad(returnTo?: string): Promise<void> {
  const body = returnTo && esPathInternoSeguro(returnTo) ? { return_to: returnTo } : {};
  const r = await authedFetch("/api/cliente/verificacion/sesion", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    const msg = typeof err?.detail === "string" ? err.detail : "No se pudo iniciar la verificación";
    toast.error(msg);
    throw new Error(msg);
  }
  const { url } = (await r.json()) as { url: string };
  window.location.assign(url);
}

// Reusa el mismo flag que el retorno de login (`?openCarrito=1`, introducido en
// dev): un único param "reabrí el carrito al volver de un desvío de auth"
// (login O verificación). El desktop lo maneja con su handler propio en
// index.tsx; este hook cubre el mobile (CartSheet en CatalogoMovil), que no
// tiene ese handler.
const RESUME_FLAG = "openCarrito";
const RESUME_VALUE = "1";

/** Al volver a una ruta del catálogo con `?openCarrito=1` (tras login o
 *  verificación), reabre el carrito. El flag vive en la URL (NO en el cart-store,
 *  que excluye drawerOpen a propósito). Corre una sola vez en mount; limpia el flag. */
export function useRetomarPedido(onRetomar: () => void): void {
  useEffect(() => {
    if (typeof window === "undefined") return;
    const sp = new URLSearchParams(window.location.search);
    if (sp.get(RESUME_FLAG) !== RESUME_VALUE) return;
    onRetomar();
    sp.delete(RESUME_FLAG);
    const url = new URL(window.location.href);
    url.search = sp.toString();
    window.history.replaceState({}, "", url.toString());
    // eslint-disable-next-line react-hooks/exhaustive-deps -- solo en mount; onRetomar se asume estable
  }, []);
}
