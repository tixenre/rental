import { useEffect } from "react";
import { toast } from "sonner";
import { authedFetch } from "./authedFetch";

export type EstadoCuenta =
  | "no-logueado"
  | "no-verificado"
  | "en-revision"
  | "rechazado"
  | "logueado-verificado"
  | "error";

export interface EstadoVerificacion {
  estado: EstadoCuenta;
  motivo?: string | null;
}

/** Lee /api/cliente/me y clasifica la cuenta por `dni_verificacion_estado`
 *  (no solo por `dni_validado_at`) — así "en revisión" y "rechazado" (con motivo)
 *  se distinguen de "todavía no verificó nada". Fuente única del pre-check de
 *  checkout (reemplaza el `me.ok` suelto de las bocas). */
export async function chequearEstadoVerificacion(): Promise<EstadoVerificacion> {
  try {
    const r = await authedFetch("/api/cliente/me");
    if (!r.ok) return { estado: r.status === 401 ? "no-logueado" : "error" };
    const me = await r.json();
    if (me?.dni_validado_at) return { estado: "logueado-verificado" };
    if (me?.dni_verificacion_estado === "en_revision") return { estado: "en-revision" };
    if (me?.dni_verificacion_estado === "rechazado") {
      return { estado: "rechazado", motivo: me?.dni_verificacion_motivo ?? null };
    }
    return { estado: "no-verificado" };
  } catch {
    return { estado: "error" };
  }
}

/** Re-chequea contra Didit el estado ACTUAL de la propia verificación (self-recheck
 *  del cliente) — cubre el webhook que puede no haber llegado todavía cuando el
 *  cliente vuelve del flujo de Didit. Silencioso: si falla, el estado se sigue
 *  leyendo de /api/cliente/me tal cual esté (no bloquea al usuario). */
export async function recheckVerificacionIdentidad(): Promise<void> {
  try {
    await authedFetch("/api/cliente/verificacion/recheck", { method: "POST" });
  } catch {
    /* best-effort — el estado real se refleja en /api/cliente/me igual */
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
// Junto a RESUME_FLAG: reabrir directo en el paso de resumen del checkout (no
// en la lista de ítems) — espeja RESUME_STEP_PARAM/RESUME_STEP_VALUE de
// CheckoutResumen.tsx (evitamos importar ese módulo acá solo por 2 strings).
const RESUME_STEP_PARAM = "carritoPaso";
const RESUME_STEP_VALUE = "resumen";

/** Al volver a una ruta del catálogo con `?openCarrito=1` (tras login o
 *  verificación), reabre el carrito. El flag vive en la URL (NO en el cart-store,
 *  que excluye drawerOpen a propósito). Corre una sola vez en mount; limpia el flag.
 *  `onRetomar` recibe `"resumen"` si además venía `?carritoPaso=resumen` (retorno
 *  desde el paso de resumen, ver CheckoutResumen.tsx) — el caller decide qué hacer. */
export function useRetomarPedido(onRetomar: (paso?: "resumen") => void): void {
  useEffect(() => {
    if (typeof window === "undefined") return;
    const sp = new URLSearchParams(window.location.search);
    if (sp.get(RESUME_FLAG) !== RESUME_VALUE) return;
    const paso = sp.get(RESUME_STEP_PARAM) === RESUME_STEP_VALUE ? "resumen" : undefined;
    onRetomar(paso);
    sp.delete(RESUME_FLAG);
    sp.delete(RESUME_STEP_PARAM);
    const url = new URL(window.location.href);
    url.search = sp.toString();
    window.history.replaceState({}, "", url.toString());
    // eslint-disable-next-line react-hooks/exhaustive-deps -- solo en mount; onRetomar se asume estable
  }, []);
}
