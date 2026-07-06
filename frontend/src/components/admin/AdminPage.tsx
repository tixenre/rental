import { type ReactNode } from "react";
import { Link, useRouterState } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";

import { cn } from "@/lib/utils";
import { matchAdminRoute } from "./adminNav";

/** Presets de ancho — una sola forma en vez de una clase Tailwind libre por
 *  ruta. form = forms simples/compactos · detail = editor de un registro ·
 *  list = tabla/listado denso · wide = default, la mayoría de las pantallas. */
const MAX_W = {
  form: "max-w-3xl",
  detail: "max-w-4xl",
  list: "max-w-6xl",
  wide: "max-w-7xl",
} as const;

type AdminPageMaxW = keyof typeof MAX_W;

/**
 * AdminPage — chrome único de página del back-office.
 *
 * Absorbe el header (eyebrow + h1), el padding del contenedor, el max-width y el
 * back-link, que hoy están copy-pasteados e inconsistentes en ~26 rutas. El
 * eyebrow sale por default del GRUPO de la ruta en `adminNav` (fuente única), así
 * que el breadcrumb queda correcto incluso en rutas con URL desalineada.
 *
 *   <AdminPage title="Unidades" actions={<Button>Nueva</Button>}>
 *     …contenido…
 *   </AdminPage>
 *
 * **Excepción documentada:** `pedidos.$id.lazy.tsx` (el editor de un pedido) NO
 * usa `AdminPage` — su topbar es una entidad viva (nombre del cliente + número +
 * `EstadoBadge` + `SaveIndicator`/WhatsApp), no un título estático, y su cuerpo es
 * una grilla de 2 columnas con rail sticky de financials — no encaja en `title`/
 * `eyebrow`/`layout="page"` ni `"fullHeight"`. No forzar el swap ahí.
 */
export function AdminPage({
  title,
  eyebrow,
  backTo,
  actions,
  description,
  maxW = "wide",
  layout = "page",
  className,
  children,
}: {
  title: string;
  /** Override del eyebrow. Default: el label del grupo de la ruta en adminNav. */
  eyebrow?: string;
  /** Back-link opcional para sub-páginas. */
  backTo?: { to: string; label: string };
  /** Acciones a la derecha del título (botones). */
  actions?: ReactNode;
  /** Bajada opcional debajo del título. */
  description?: ReactNode;
  /** Preset de ancho (ver `MAX_W`). Solo aplica con `layout="page"`. */
  maxW?: AdminPageMaxW;
  /** "page" (default) = contenedor centrado, capado por `maxW`. "fullHeight" =
   *  ocupa el viewport bajo el topbar (flex column, header fijo, `children`
   *  se encarga de su propio scroll) — para layouts master-detail; sin `maxW`
   *  (ancho completo). */
  layout?: "page" | "fullHeight";
  className?: string;
  children: ReactNode;
}) {
  const pathname = useRouterState({ select: (r) => r.location.pathname });
  const route = matchAdminRoute(pathname);
  const eyebrowText = eyebrow ?? route?.group ?? "Back-office";

  const header = (
    <header className={layout === "fullHeight" ? "shrink-0 px-4 py-4 md:px-6" : "mb-6"}>
      {backTo && (
        <Link
          to={backTo.to}
          className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-ink"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          {backTo.label}
        </Link>
      )}
      <div className="t-eyebrow">{eyebrowText}</div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h1 className="t-h1 text-ink">{title}</h1>
          {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>
    </header>
  );

  if (layout === "fullHeight") {
    return (
      <div className="flex h-[calc(100dvh-var(--admin-topbar-h,56px))] min-h-0 flex-col">
        {header}
        <div className={cn("min-h-0 flex-1", className)}>{children}</div>
      </div>
    );
  }

  return (
    <div className={cn("mx-auto px-4 py-6 md:px-6", MAX_W[maxW], className)}>
      {header}
      {children}
    </div>
  );
}
