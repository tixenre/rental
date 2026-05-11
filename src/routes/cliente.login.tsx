import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

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
  not_allowed:    "Tu cuenta de Google no está autorizada.",
  state_mismatch: "Error de seguridad en el flujo de login. Intentá de nuevo.",
  token_error:    "No se pudo completar la autenticación con Google. Intentá de nuevo.",
  userinfo_error: "No se pudo obtener tu información de Google. Intentá de nuevo.",
  no_email:       "Google no devolvió un email. Verificá los permisos de tu cuenta.",
  no_code:        "Google no devolvió el código de autorización. Intentá de nuevo.",
};

function ClienteLoginPage() {
  const [error, setError] = useState<string | null>(null);

  const { data: logoSetting } = useQuery({
    queryKey: ["settings", "logo_url"],
    queryFn: () =>
      fetch("/api/settings/logo_url").then((r) => (r.ok ? r.json() : null)).catch(() => null),
    staleTime: 5 * 60 * 1000,
  });
  const logoUrl: string | null = logoSetting?.value ?? null;

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const errCode = params.get("error");
    if (errCode) setError(ERROR_MESSAGES[errCode] ?? `Error: ${errCode}`);
  }, []);

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Header con branding */}
      <header className="border-b hairline px-6 py-4 flex items-center">
        <Link to="/" className="flex items-center gap-2">
          {logoUrl ? (
            <img src={logoUrl} alt="Rambla Rental" className="h-9 w-auto object-contain" />
          ) : (
            <>
              <span className="wordmark text-2xl text-amber leading-none">rambla</span>
              <span className="font-mono text-[9px] uppercase tracking-[0.3em] text-foreground/70 border-l hairline pl-2">
                Rental
              </span>
            </>
          )}
        </Link>
      </header>

      {/* Card de login */}
      <div className="flex-1 grid place-items-center px-4 py-12">
      <div className="w-full max-w-sm rounded-2xl border hairline bg-surface p-8 shadow-sm space-y-6">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            Portal de clientes
          </div>
          <h1 className="mt-1 font-display text-2xl text-ink">Acceso</h1>
          <p className="mt-1 text-xs text-muted-foreground">
            Ingresá con la cuenta de Google con la que hiciste tu reserva.
          </p>
        </div>

        {error && (
          <div className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">
            {error}
          </div>
        )}

        <button
          onClick={() => { window.location.href = "/cliente/auth/google"; }}
          className="w-full flex items-center justify-center gap-3 rounded-md border hairline bg-background py-2.5 text-sm font-medium text-ink transition hover:bg-surface active:scale-[0.98]"
        >
          <GoogleIcon />
          Entrar con Google
        </button>
      </div>
      </div>
    </div>
  );
}

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9 3.2l6.7-6.7C35.7 2.5 30.2 0 24 0 14.6 0 6.6 5.4 2.7 13.3l7.8 6C12.4 13 17.8 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v8.5h12.7c-.6 3-2.3 5.5-4.8 7.2l7.6 5.9c4.4-4.1 7-10.1 7-17.1z" />
      <path fill="#FBBC05" d="M10.5 28.7A14.6 14.6 0 0 1 9.5 24c0-1.6.3-3.2.8-4.7l-7.8-6A23.9 23.9 0 0 0 0 24c0 3.9.9 7.5 2.7 10.7l7.8-6z" />
      <path fill="#34A853" d="M24 48c6.2 0 11.4-2 15.2-5.5l-7.6-5.9c-2 1.4-4.6 2.2-7.6 2.2-6.2 0-11.5-4.2-13.4-9.8l-7.8 6C6.6 42.6 14.6 48 24 48z" />
    </svg>
  );
}
