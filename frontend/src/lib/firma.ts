/**
 * lib/firma.ts — firma "on-the-fly" de una acción sensible con passkey (Fase 5 identidad #1098).
 *
 * El portero de checkout (`services/checkout`) acepta la firma como
 * `firma_ok = has_recent_stepup() OR session_confirmed`. El **step-up con passkey** es la
 * modalidad fuerte; el fallback ("Confirmo y acepto" por sesión) es para quien no tiene llave.
 *
 * Esto agrega el **on-the-fly**: si la cuenta NO tiene passkey, en vez de caer al fallback
 * débil se la crea **en el momento** (un gesto: Face ID / huella / PIN) y se firma con ella.
 * Así la modalidad fuerte la usa todo el mundo, sin fricción.
 *
 * `tienePasskey` lo pasa el caller (lo sabe de antes — `listPasskeys` / un flag): así no hay
 * un `await` de red entre el click y el prompt de WebAuthn (que rompería el user-gesture).
 *
 * Patrón de uso en el checkout (dos caminos):
 *   onClick "Firmar con mi llave":  const r = await firmarConPasskey(tienePasskey);
 *                                   if (r === "passkey") confirmarPedido();
 *                                   else  // "sin-soporte" | "cancelado" → ofrecé el fallback
 *   onClick "Confirmo y acepto":    confirmarPedido();   // fallback por sesión
 */
import { passkeySupported, registerPasskey, stepUpWithPasskey } from "@/lib/passkey";

export type ResultadoFirma = "passkey" | "sin-soporte" | "cancelado";

/**
 * Garantiza un step-up con passkey (firma fuerte). Si `tienePasskey` es false, crea la llave
 * on-the-fly y firma con ella. Devuelve:
 *   · "passkey"     → firmó fuerte (el portero verá `firma_ok` por el step-up).
 *   · "sin-soporte" → el device/navegador no soporta passkeys → usá el fallback.
 *   · "cancelado"   → el usuario canceló el prompt o falló → usá el fallback.
 *
 * La PRIMERA vez sin llave son dos prompts seguidos (crear + firmar); las siguientes, uno.
 */
export async function firmarConPasskey(tienePasskey: boolean): Promise<ResultadoFirma> {
  if (!passkeySupported()) return "sin-soporte";
  try {
    if (!tienePasskey) {
      // On-the-fly: la crea en el momento (Face ID / huella / PIN), sin tipear nada.
      await registerPasskey("cliente");
    }
    // Deja la marca de corta vida que el portero lee como firma (has_recent_stepup → firma_ok).
    await stepUpWithPasskey();
    return "passkey";
  } catch {
    return "cancelado";
  }
}
