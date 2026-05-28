import { createFileRoute } from "@tanstack/react-router";
import { GoogleIcon } from "@/components/ui/GoogleIcon";
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
  not_allowed: "Tu cuenta de Google no está autorizada.",
  state_mismatch: "Error de seguridad en el flujo de login. Intentá de nuevo.",
  token_error: "No se pudo completar la autenticación con Google. Intentá de nuevo.",
  userinfo_error: "No se pudo obtener tu información de Google. Intentá de nuevo.",
  no_email: "Google no devolvió un email. Verificá los permisos de tu cuenta.",
  no_code: "Google no devolvió el código de autorización. Intentá de nuevo.",
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
              Ingresá con la cuenta de Google con la que hiciste tu reserva para ver tus pedidos,
              descargar remitos y consultar pagos.
            </p>
          </div>

          {error && (
            <div className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">
              {error}
            </div>
          )}

          <button
            onClick={() => {
              window.location.href = "/cliente/auth/google";
            }}
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
