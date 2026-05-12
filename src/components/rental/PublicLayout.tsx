import type { ReactNode } from "react";
import { TopBar, type TopBarProps } from "./TopBar";
import { Footer } from "./Footer";

/**
 * Layout shell para rutas públicas: TopBar + main + Footer.
 *
 * Reemplaza el patrón disperso de "cada ruta importa TopBar y Footer manualmente"
 * que generaba drift (ej. `/estudio` se olvidaba el `<Footer />`).
 *
 * NO usar en /admin/* (tienen `AdminLayout` con sidebar).
 *
 * Para `/cliente/*` post-login, usar `<PublicLayout topBar={{ variant: "cliente", ... }}>`.
 */
export function PublicLayout({
  children,
  topBar,
}: {
  children: ReactNode;
  topBar?: TopBarProps;
}) {
  return (
    <div className="min-h-dvh flex flex-col bg-background text-foreground">
      <TopBar {...topBar} />
      <main className="flex-1">{children}</main>
      <Footer />
    </div>
  );
}
