import { authedPostJson } from "./authedFetch";

export interface FaltanItem {
  check: string;
  mensaje: string;
  accion?: string;
}

export interface CheckoutValidarResult {
  listo: boolean;
  faltan: FaltanItem[];
}

export async function aceptarTyc(): Promise<void> {
  await authedPostJson("/api/checkout/aceptar-tyc", {});
}

export async function validarCheckout(
  sessionId: string,
  sessionConfirmed = false,
): Promise<CheckoutValidarResult> {
  return authedPostJson<CheckoutValidarResult>("/api/checkout/validar", {
    session_id: sessionId,
    session_confirmed: sessionConfirmed,
  });
}
