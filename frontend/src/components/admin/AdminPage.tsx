import { type ReactNode } from "react";
import { Link, useRouterState } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";

import { cn } from "@/lib/utils";
import { matchAdminRoute } from "./adminNav";

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
 */
export function AdminPage({
  title,
  eyebrow,
  backTo,
  actions,
  description,
  maxW = "max-w-7xl",
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
  maxW?: string;
  className?: string;
  children: ReactNode;
}) {
  const pathname = useRouterState({ select: (r) => r.location.pathname });
  const route = matchAdminRoute(pathname);
  const eyebrowText = eyebrow ?? route?.group ?? "Back-office";

  return (
    <div className={cn("mx-auto px-4 py-6 md:px-6", maxW, className)}>
      <header className="mb-6">
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
      {children}
    </div>
  );
}
