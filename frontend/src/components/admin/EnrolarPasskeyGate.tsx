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
import { BackOfficeAuthCard } from "@/components/admin/BackOfficeAuthCard";
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
      <BackOfficeAuthCard
        title="Registrá tu clave de acceso"
        description="Como segundo factor, tu cuenta de admin necesita una clave de acceso (huella, rostro o PIN de este dispositivo). Se registra una sola vez — de ahí en más la vas a usar para confirmar cada login con Google."
      >
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
      </BackOfficeAuthCard>
    );
  }

  return <>{children}</>;
}
