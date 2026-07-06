/**
 * BackOfficeAuthCard — cascarón único de las pantallas de auth del back-office
 * (login, confirmar 2º factor, registrar passkey on-the-fly). Antes estaba
 * copiado 3 veces (2 en admin.login.tsx + 1 en EnrolarPasskeyGate) — "reusar
 * no recrear" del DS. Header+Logo, card centrada, eyebrow, título, descripción
 * y el bloque de error son siempre los mismos; `children` son las acciones
 * (botones), que sí varían por pantalla.
 */
import type { ReactNode } from "react";

import { Logo } from "@/components/rental/shell/Logo";

export function BackOfficeAuthCard({
  title,
  description,
  error,
  children,
}: {
  title: string;
  description: ReactNode;
  error?: string | null;
  children: ReactNode;
}) {
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
            <h1 className="mt-1 font-display text-2xl text-ink">{title}</h1>
            <p className="mt-1 text-xs text-muted-foreground leading-relaxed">{description}</p>
          </div>

          {error && (
            <div className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">
              {error}
            </div>
          )}

          {children}
        </div>
      </div>
    </div>
  );
}
