/**
 * EnrolarPasskeyGate — 2º factor obligatorio para admin (criterio del dueño).
 *
 * Sin ninguna passkey enrolada todavía, bloquea el resto del back-office con un
 * enrolamiento on-the-fly: la próxima vez que un admin entra con Google, esta
 * pantalla le crea la clave de acceso ahí mismo (un solo toque, reusa
 * `registerPasskey` — el mismo primitivo de Settings). De acá en más, esa cuenta
 * tiene una passkey → `auth/google.py::auth_callback` deja de mintear sesión solo
 * con Google y exige confirmarla (ver /admin/login?paso=passkey).
 *
 * Se salta a sí mismo si el browser no soporta WebAuthn (no bloquear a un admin
 * en un navegador viejo) — mismo fallback que `PasskeyManager`.
 */
import { useEffect, useState } from "react";
import { KeyRound } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/design-system/ui/button";
import { Logo } from "@/components/rental/Logo";
import {
  listPasskeys,
  passkeyErrorMessage,
  passkeySupported,
  registerPasskey,
} from "@/lib/passkey";

type Estado = "chequeando" | "falta-enrolar" | "listo";

export function EnrolarPasskeyGate({ children }: { children: React.ReactNode }) {
  const [estado, setEstado] = useState<Estado>("chequeando");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!passkeySupported()) {
      setEstado("listo"); // navegador sin soporte: no bloqueamos al admin
      return;
    }
    let alive = true;
    listPasskeys("admin")
      .then((creds) => alive && setEstado(creds.length > 0 ? "listo" : "falta-enrolar"))
      .catch(() => alive && setEstado("listo")); // fail-open: un error de red no bloquea el login
    return () => {
      alive = false;
    };
  }, []);

  if (estado === "chequeando") {
    return (
      <div className="min-h-screen grid place-items-center text-sm text-muted-foreground">
        Cargando…
      </div>
    );
  }

  if (estado === "falta-enrolar") {
    return (
      <div className="min-h-dvh bg-background flex flex-col">
        <header className="border-b hairline px-4 py-3 md:px-6 flex items-center">
          <Logo size="md" linkTo="/" />
        </header>
        <div className="flex-1 grid place-items-center px-4 py-12">
          <div className="w-full max-w-sm rounded-2xl border hairline bg-surface p-8 shadow-sm space-y-6">
            <div>
              <div className="font-mono text-2xs uppercase tracking-[0.2em] text-muted-foreground">
                Back-office
              </div>
              <h1 className="mt-1 font-display text-2xl text-ink">Registrá tu clave de acceso</h1>
              <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
                Como segundo factor, tu cuenta de admin necesita una clave de acceso (huella, rostro
                o PIN de este dispositivo). Se registra una sola vez — de ahí en más la vas a usar
                para confirmar cada login con Google.
              </p>
            </div>
            <Button
              type="button"
              className="w-full"
              loading={busy}
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await registerPasskey("admin");
                  toast.success("Clave de acceso registrada");
                  setEstado("listo");
                } catch (e) {
                  toast.error(passkeyErrorMessage(e));
                } finally {
                  setBusy(false);
                }
              }}
            >
              <KeyRound /> {busy ? "Registrando…" : "Registrar clave de acceso"}
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
