/**
 * contabilidad.liquidacion.lazy.tsx — Liquidación (devengado) dentro de Finanzas.
 *
 * El reporte de liquidación (cuánto le toca a cada dueño/socio, por mes/año, con
 * cierre de mes, reconciliación, export CSV y envío por mail) vive acá, en Finanzas
 * — su lugar natural. El componente es compartido (`@/components/admin/LiquidacionReporte`).
 */
import { createLazyFileRoute } from "@tanstack/react-router";

import { AdminPage } from "@/components/admin/AdminPage";
import { useDocumentTitle } from "@/lib/use-document-title";
import { LiquidacionReporte } from "@/components/admin/LiquidacionReporte";

export const Route = createLazyFileRoute("/admin/contabilidad/liquidacion")({
  component: LiquidacionPage,
});

function LiquidacionPage() {
  useDocumentTitle("Liquidación · Finanzas");
  return (
    <AdminPage
      title="Liquidación"
      description="Cuánto generó cada equipo y le toca a cada dueño/socio (devengado), por mes y por año — con cierre de mes, export CSV y envío por mail."
      backTo={{ to: "/admin/contabilidad", label: "Tablero" }}
    >
      <LiquidacionReporte />
    </AdminPage>
  );
}
