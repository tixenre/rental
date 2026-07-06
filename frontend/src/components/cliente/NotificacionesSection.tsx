/**
 * NotificacionesSection.tsx — tab "Notificaciones" del portal cliente.
 * Extraído de ClientePortalHelpers.tsx.
 */
import { Bell } from "lucide-react";
import { EmptyState } from "@/design-system/composites/EmptyState";

export function NotificacionesSection() {
  return (
    <div className="px-5 lg:px-10 pt-8">
      <div className="flex items-baseline justify-between gap-3 mb-8">
        <h2 className="font-display text-22 font-black text-ink tracking-[-0.01em]">
          notificaciones.
        </h2>
      </div>
      <EmptyState
        icon={<Bell className="h-6 w-6" strokeWidth={1.5} />}
        title="Sin notificaciones"
        sub="Cuando haya novedades sobre tus pedidos o documentos aparecerán acá."
        className="rounded-xl border border-dashed hairline px-6 py-[60px]"
      />
      {/* TODO: conectar a /api/cliente/notificaciones cuando el endpoint esté disponible */}
    </div>
  );
}
