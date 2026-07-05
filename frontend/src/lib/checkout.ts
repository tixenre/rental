import { authedFetch, authedPostJson } from "./authedFetch";

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

/** Preview del contrato del pedido EN CURSO (simulación, antes de crearlo) —
 *  devuelve el HTML completo tal cual lo arma el backend (`_contrato_html`,
 *  marcado con el aviso de simulación). No es JSON, por eso no usa
 *  `authedJson` — se lee como texto. */
export async function obtenerContratoPreviewHtml(
  sessionId: string,
  target?: { perfilFiscalId?: number; productoraId?: number },
): Promise<string> {
  const res = await authedFetch("/api/checkout/contrato-preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      perfil_fiscal_id: target?.perfilFiscalId ?? null,
      productora_id: target?.productoraId ?? null,
    }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    let message = "";
    try {
      message = JSON.parse(text)?.detail ?? "";
    } catch {
      /* no era JSON */
    }
    throw new Error(message || "No pudimos generar el preview del contrato.");
  }
  return res.text();
}
