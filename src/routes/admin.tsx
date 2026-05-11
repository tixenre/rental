import { createFileRoute } from "@tanstack/react-router";
import { lazy, Suspense } from "react";

// Lazy-load del layout de admin: Rollup lo emite como chunk separado y NO
// lo precarga. Visitors del catálogo público no lo descargan hasta navegar
// a /admin/*. Ahorra ~240 KB raw / ~60 KB gzipped en el bundle inicial.
const AdminLayout = lazy(() =>
  import("@/components/admin/AdminLayout").then((m) => ({
    default: m.AdminLayout,
  })),
);

export const Route = createFileRoute("/admin")({
  head: () => ({
    meta: [
      { title: "Backoffice — Rambla Rental" },
      { name: "robots", content: "noindex, nofollow" },
    ],
  }),
  component: () => (
    <Suspense
      fallback={
        <div className="min-h-screen grid place-items-center text-sm text-muted-foreground">
          Cargando…
        </div>
      }
    >
      <AdminLayout />
    </Suspense>
  ),
});
