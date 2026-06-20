/**
 * contabilidad.liquidacion.lazy.tsx — Liquidación (devengado) dentro de Finanzas.
 *
 * El reporte de liquidación (cuánto le toca a cada dueño/socio, por mes/año, con
 * cierre de mes, reconciliación, export CSV y envío por mail) vive acá, en Finanzas
 * — su lugar natural. El componente es compartido (`@/components/admin/LiquidacionReporte`).
 */
import { createLazyFileRoute, Link } from "@tanstack/react-router";

import { useDocumentTitle } from "@/lib/use-document-title";
import { LiquidacionReporte } from "@/components/admin/LiquidacionReporte";

export const Route = createLazyFileRoute("/admin/contabilidad/liquidacion")({
  component: LiquidacionPage,
});

function LiquidacionPage() {
  useDocumentTitle("Liquidación · Finanzas");
  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-7xl mx-auto">
      <header className="flex items-start justify-between gap-4">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Back-office · Finanzas
          </div>
          <h1 className="font-display text-3xl text-ink">Liquidación</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Cuánto generó cada equipo y le toca a cada dueño/socio (devengado), por mes y por año —
            con cierre de mes, export CSV y envío por mail.
          </p>
        </div>
        <Link
          to="/admin/contabilidad"
          className="shrink-0 h-9 rounded-md border hairline px-3 text-sm flex items-center hover:bg-muted/40"
        >
          ← Tablero
        </Link>
      </header>

      <LiquidacionReporte />
    </div>
  );
}
