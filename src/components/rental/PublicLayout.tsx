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
 *
 * IMPORTANTE — alcance respecto a mobile:
 * Este wrapper provee TopBar y Footer que ya son mobile-aware. Pero NO garantiza
 * que el contenido de cada ruta pase el "criterio mobile" del proyecto
 * (`docs/MOBILE_AUDIT.md`). Cada página tiene que tener su propio layout mobile
 * pensado — dual render, sticky bar, sheet fullscreen, lista card-based, etc.
 * Envolver con `<PublicLayout>` no exime de la auditoría mobile.
 */
export function PublicLayout({
  children,
  topBar,
  searchValue,
  onSearch,
}: {
  children: ReactNode;
  topBar?: TopBarProps;
  searchValue?: string;
  onSearch?: (value: string) => void;
}) {
  return (
    <div className="min-h-dvh flex flex-col bg-background text-foreground">
      <TopBar {...topBar} searchValue={searchValue} onSearch={onSearch} />
      <main className="flex-1">{children}</main>
      <Footer />
    </div>
  );
}
