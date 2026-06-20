import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { authedFetch } from "@/lib/authedFetch";
import { Logo } from "@/components/rental/Logo";
import { GoogleIcon } from "@/components/ui/GoogleIcon";

export const Route = createFileRoute("/admin/login")({
  head: () => ({
    meta: [{ title: "Login · Back Office" }, { name: "robots", content: "noindex, nofollow" }],
  }),
  component: AdminLoginPage,
});

const ERROR_MESSAGES: Record<string, string> = {
  not_allowed: "Tu cuenta de Google no está autorizada para acceder al admin.",
  state_mismatch: "Error de seguridad en el flujo de login. Intentá de nuevo.",
  token_error: "No se pudo completar la autenticación con Google. Intentá de nuevo.",
  userinfo_error: "No se pudo obtener tu información de Google. Intentá de nuevo.",
  no_email: "Google no devolvió un email. Verificá los permisos de tu cuenta.",
  no_code: "Google no devolvió el código de autorización. Intentá de nuevo.",
};

function AdminLoginPage() {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [devMode, setDevMode] = useState(false);
  const [googleEnabled, setGoogleEnabled] = useState(true);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const errCode = params.get("error");
    if (errCode) {
      setError(ERROR_MESSAGES[errCode] ?? `Error: ${errCode}`);
    }
    // Flag `denied=1` lo setea AdminLayout cuando el usuario está logueado
    // en Google pero su email no está en ADMIN_EMAILS.
    if (params.get("denied") === "1") {
      setError(ERROR_MESSAGES.not_allowed);
    }

    authedFetch("/auth/me").then(async (r) => {
      if (!r.ok) return;
      // Solo redirect al admin si el usuario es admin. Sino se queda
      // viendo la pantalla de login (con el mensaje si vino con denied).
      const data = (await r.json()) as { is_admin?: boolean };
      if (data.is_admin) navigate({ to: "/admin" });
    });

    authedFetch("/auth/config").then(async (r) => {
      if (r.ok) {
        const data = await r.json();
        setDevMode(data.dev_mode ?? false);
        setGoogleEnabled(data.google_enabled ?? true);
      }
    });
  }, [navigate]);

  function handleGoogleLogin() {
    window.location.href = "/auth/google";
  }

  function handleDevLogin() {
    window.location.href = "/auth/dev-login";
  }

  return (
    <div className="min-h-dvh bg-background flex flex-col">
      <header className="border-b hairline px-4 py-3 md:px-6 flex items-center">
        <Logo size="md" linkTo="/" />
      </header>
      <div className="flex-1 grid place-items-center px-4 py-12">
        <div className="w-full max-w-sm rounded-2xl border hairline bg-surface p-8 shadow-sm space-y-6">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              Back-office
            </div>
            <h1 className="mt-1 font-display text-2xl text-ink">Acceso admin</h1>
            <p className="mt-1 text-xs text-muted-foreground">
              {devMode
                ? "Modo desarrollo — sin OAuth requerido."
                : "Ingresá con tu cuenta de Google autorizada."}
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
              className="w-full flex items-center justify-center gap-3 rounded-md border hairline bg-amber/10 border-amber/30 py-2.5 text-sm font-medium text-ink transition hover:bg-amber/15 active:scale-[0.98]"
            >
              Entrar en modo desarrollo
            </button>
          )}

          {googleEnabled && (
            <button
              onClick={handleGoogleLogin}
              className="w-full flex items-center justify-center gap-3 rounded-md border hairline bg-background py-2.5 text-sm font-medium text-ink transition hover:bg-surface active:scale-[0.98]"
            >
              <GoogleIcon />
              Entrar con Google
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
