import { createFileRoute } from "@tanstack/react-router";
import { GoogleIcon } from "@/design-system/ui/GoogleIcon";
import { useEffect, useState } from "react";
import { TopBar } from "@/components/rental/TopBar";
import { authedFetch } from "@/lib/authedFetch";
import {
  loginWithPasskey,
  signupWithPasskey,
  passkeyErrorMessage,
  passkeyLoginErrorMessage,
  passkeySupported,
} from "@/lib/passkey";
import { Button } from "@/design-system/ui/button";
import { KeyRound } from "lucide-react";

export const Route = createFileRoute("/cliente/login")({
  head: () => ({
    meta: [
      { title: "Acceso clientes — Rambla Rental" },
      { name: "robots", content: "noindex, nofollow" },
    ],
  }),
  component: ClienteLoginPage,
});

const ERROR_MESSAGES: Record<string, string> = {
  not_allowed: "Tu cuenta de Google no está autorizada.",
  state_mismatch: "Error de seguridad en el flujo de login. Intentá de nuevo.",
  token_error: "No se pudo completar la autenticación con Google. Intentá de nuevo.",
  userinfo_error: "No se pudo obtener tu información de Google. Intentá de nuevo.",
  no_email: "Google no devolvió un email. Verificá los permisos de tu cuenta.",
  no_code: "Google no devolvió el código de autorización. Intentá de nuevo.",
};

function ClienteLoginPage() {
  const [error, setError] = useState<string | null>(null);
  const [devMode, setDevMode] = useState(false);
  const [supported] = useState(() => passkeySupported());
  const [passkeyBusy, setPasskeyBusy] = useState(false);
  const [signupBusy, setSignupBusy] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const errCode = params.get("error");
    if (errCode) setError(ERROR_MESSAGES[errCode] ?? `Error: ${errCode}`);

    authedFetch("/auth/config").then(async (r) => {
      if (r.ok) {
        const data = await r.json();
        setDevMode(data.dev_mode ?? false);
      }
    });
  }, []);

  function handleGoogleLogin() {
    const params = new URLSearchParams(window.location.search);
    const from = params.get("from");
    const next = from === "carrito" ? "/?openCarrito=1" : null;
    window.location.href = next
      ? `/cliente/auth/google?next=${encodeURIComponent(next)}`
      : "/cliente/auth/google";
  }

  function handleDevLogin() {
    window.location.href = "/auth/dev-login-cliente";
  }

  async function handlePasskeySignup() {
    if (signupBusy || passkeyBusy) return;
    setError(null);
    setSignupBusy(true);
    try {
      await signupWithPasskey();
      window.location.href = "/cliente/portal";
    } catch (e) {
      setError(passkeyErrorMessage(e));
      setSignupBusy(false);
    }
  }

  async function handlePasskeyLogin() {
    if (passkeyBusy || signupBusy) return;
    setError(null);
    setPasskeyBusy(true);
    try {
      await loginWithPasskey();
      window.location.href = "/cliente/portal";
    } catch (e) {
      setError(passkeyLoginErrorMessage(e));
      setPasskeyBusy(false);
    }
  }

  return (
    <div className="min-h-dvh bg-background flex flex-col">
      <TopBar variant="cliente" />

      <div className="flex-1 grid place-items-center px-6 py-8">
        <div className="w-full max-w-[400px] rounded-[20px] border hairline bg-surface p-8 sm:px-8 sm:py-9 shadow-[0_12px_40px_-10px_rgba(0,0,0,0.08)] flex flex-col gap-[22px]">
          <div>
            <div className="font-mono text-2xs uppercase tracking-[0.26em] text-muted-foreground">
              Portal de clientes
            </div>
            {/* eslint-disable-next-line no-restricted-syntax -- display heading: entre text-3xl (30px) y text-4xl (36px), óptico */}
            <h1 className="font-display text-[32px] font-black text-ink leading-none tracking-[-0.015em] mt-1.5">
              Acceso
            </h1>
            <p className="font-sans text-sm text-muted-foreground leading-[1.55] mt-1.5">
              Creá tu cuenta o ingresá para ver tus pedidos, descargar remitos y consultar pagos.
              Sin contraseñas.
            </p>
          </div>

          {error && (
            <div className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">
              {error}
            </div>
          )}

          {devMode && (
            <button
              onClick={handleDevLogin}
              className="w-full flex items-center justify-center gap-3 rounded-md border hairline bg-amber/10 border-amber/30 py-[13px] text-sm font-medium text-ink transition hover:bg-amber/15 active:scale-[0.98]"
            >
              Entrar en modo desarrollo
            </button>
          )}

          {/* Alta passwordless (estilo Vercel): el CTA primario crea la cuenta con una
              passkey directo, sin tipear nada. Es la jugada de marca ink→accent del DS. */}
          {supported && (
            <div className="flex flex-col gap-2">
              <Button
                variant="primary"
                onClick={handlePasskeySignup}
                loading={signupBusy}
                className="w-full h-auto py-[13px] text-sm font-semibold"
              >
                {!signupBusy && <KeyRound className="h-4 w-4" />}
                {signupBusy ? "Creando tu cuenta…" : "Crear cuenta con clave de acceso"}
              </Button>
              <p className="text-center font-sans text-2xs text-muted-foreground leading-[1.5]">
                Sin contraseña — usás tu huella, Face ID o el PIN del dispositivo.
              </p>
            </div>
          )}

          {/* El divisor separa el alta (arriba) del ingreso (abajo); sin passkey solo
              hay ingreso → no hace falta. */}
          {supported && (
            <div className="flex items-center gap-3 font-mono text-2xs uppercase tracking-[0.2em] text-muted-foreground before:content-[''] before:flex-1 before:h-px before:bg-[var(--hairline)] after:content-[''] after:flex-1 after:h-px after:bg-[var(--hairline)]">
              ya tenés cuenta
            </div>
          )}

          <button
            onClick={handleGoogleLogin}
            className="flex items-center justify-center gap-2.5 rounded-md border-[1.5px] hairline bg-card py-[13px] font-sans text-sm font-semibold text-ink transition hover:border-ink hover:bg-background"
          >
            <GoogleIcon />
            Entrar con Google
          </button>

          {supported && (
            <button
              onClick={handlePasskeyLogin}
              disabled={passkeyBusy}
              className="flex items-center justify-center gap-2.5 rounded-md border-[1.5px] hairline bg-card py-[13px] font-sans text-sm font-semibold text-ink transition hover:border-ink hover:bg-background disabled:opacity-60"
            >
              <KeyRound className="h-4 w-4" />
              {passkeyBusy ? "Verificando…" : "Entrar con clave de acceso"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
