import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Logo } from "@/components/rental/Logo";
import { useBusinessPhone } from "@/lib/business";
import { whatsappLink } from "@/lib/whatsapp";

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
  const businessPhone = useBusinessPhone();
  const waHref = whatsappLink({
    phone: businessPhone,
    message: "Hola, quiero crear una cuenta para alquilar equipos.",
  });

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const errCode = params.get("error");
    if (errCode) setError(ERROR_MESSAGES[errCode] ?? `Error: ${errCode}`);
  }, []);

  return (
    <div className="min-h-dvh bg-background flex flex-col">
      <header className="border-b hairline px-6 py-[18px]">
        <Logo size="md" linkTo="/" />
      </header>

      <div className="flex-1 grid place-items-center px-6 py-8">
        <div className="w-full max-w-[400px] rounded-[20px] border hairline bg-surface p-8 sm:px-8 sm:py-9 shadow-[0_12px_40px_-10px_rgba(0,0,0,0.08)] flex flex-col gap-[22px]">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.26em] text-muted-foreground">
              Portal de clientes
            </div>
            <h1 className="font-display text-[32px] font-black text-ink leading-none tracking-[-0.015em] mt-1.5">
              Acceso
            </h1>
            <p className="font-sans text-[13px] text-muted-foreground leading-[1.55] mt-1.5">
              Ingresá con la cuenta de Google con la que hiciste tu reserva
              para ver tus pedidos, descargar remitos y consultar pagos.
            </p>
          </div>

          {error && (
            <div className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">
              {error}
            </div>
          )}

          <button
            onClick={() => { window.location.href = "/cliente/auth/google"; }}
            className="flex items-center justify-center gap-2.5 rounded-md border-[1.5px] hairline bg-card py-[13px] font-sans text-sm font-semibold text-ink transition hover:border-ink hover:bg-background"
          >
            <GoogleIcon />
            Entrar con Google
          </button>

          <div className="flex items-center gap-3 font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground before:content-[''] before:flex-1 before:h-px before:bg-[var(--hairline)] after:content-[''] after:flex-1 after:h-px after:bg-[var(--hairline)]">
            o
          </div>

          <div className="text-center font-sans text-xs text-muted-foreground">
            ¿No tenés cuenta todavía?{" "}
            {waHref ? (
              <a
                href={waHref}
                target="_blank"
                rel="noopener noreferrer"
                className="text-ink border-b border-ink pb-px hover:text-amber hover:border-amber transition"
              >
                Hablanos por WhatsApp
              </a>
            ) : (
              <span className="text-ink">Escribinos para crear tu cuenta.</span>
            )}
          </div>
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
