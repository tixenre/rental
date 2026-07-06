/**
 * NotificacionesSection.tsx — tab "Notificaciones" del portal cliente.
 * Extraído de ClientePortalHelpers.tsx.
 */
import { Bell } from "lucide-react";

export function NotificacionesSection() {
  return (
    <div className="px-5 lg:px-10 pt-8">
      <div className="flex items-baseline justify-between gap-3 mb-8">
        <h2 className="font-display text-22 font-black text-ink tracking-[-0.01em]">
          notificaciones.
        </h2>
      </div>
      <div className="rounded-xl border border-dashed hairline px-6 py-[60px] text-center">
        <div className="mx-auto mb-3.5 grid h-14 w-14 place-items-center rounded-full bg-amber-soft text-amber">
          <Bell className="h-6 w-6" strokeWidth={1.5} />
        </div>
        <div className="font-display text-xl font-black text-ink mb-1.5">Sin notificaciones</div>
        <div className="font-sans text-sm text-muted-foreground max-w-[30ch] mx-auto">
          Cuando haya novedades sobre tus pedidos o documentos aparecerán acá.
        </div>
        {/* TODO: conectar a /api/cliente/notificaciones cuando el endpoint esté disponible */}
      </div>
    </div>
  );
}
