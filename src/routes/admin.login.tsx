import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { authedFetch } from "@/lib/authedFetch";
import { Logo } from "@/components/rental/Logo";

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
            <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
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
              className="w-full flex items-center justify-center gap-3 rounded-md border hairline bg-amber-50 border-amber-300 py-2.5 text-sm font-medium text-amber-900 transition hover:bg-amber-100 active:scale-[0.98]"
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

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
      <path
        fill="#EA4335"
        d="M24 9.5c3.5 0 6.6 1.2 9 3.2l6.7-6.7C35.7 2.5 30.2 0 24 0 14.6 0 6.6 5.4 2.7 13.3l7.8 6C12.4 13 17.8 9.5 24 9.5z"
      />
      <path
        fill="#4285F4"
        d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v8.5h12.7c-.6 3-2.3 5.5-4.8 7.2l7.6 5.9c4.4-4.1 7-10.1 7-17.1z"
      />
      <path
        fill="#FBBC05"
        d="M10.5 28.7A14.6 14.6 0 0 1 9.5 24c0-1.6.3-3.2.8-4.7l-7.8-6A23.9 23.9 0 0 0 0 24c0 3.9.9 7.5 2.7 10.7l7.8-6z"
      />
      <path
        fill="#34A853"
        d="M24 48c6.2 0 11.4-2 15.2-5.5l-7.6-5.9c-2 1.4-4.6 2.2-7.6 2.2-6.2 0-11.5-4.2-13.4-9.8l-7.8 6C6.6 42.6 14.6 48 24 48z"
      />
    </svg>
  );
}
