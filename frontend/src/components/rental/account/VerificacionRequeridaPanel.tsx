import { Clock, ShieldAlert, ShieldCheck } from "lucide-react";
import { Button } from "@/design-system/ui/button";

export type VerificacionPanelEstado = "no-verificado" | "en-revision" | "rechazado";

export function VerificacionRequeridaPanel({
  estado = "no-verificado",
  motivo,
  onVerificar,
  iniciando,
}: {
  estado?: VerificacionPanelEstado;
  motivo?: string | null;
  onVerificar: () => void;
  iniciando?: boolean;
}) {
  if (estado === "en-revision") {
    return (
      <div role="status" className="rounded-md border border-amber/40 bg-amber-soft p-3 space-y-1">
        <p className="text-sm font-medium text-ink flex items-center gap-2">
          <Clock className="h-4 w-4 shrink-0" />
          Tu identidad está en revisión
        </p>
        <p className="text-xs text-muted-foreground">
          Ya recibimos tus datos y los estamos revisando — te avisamos por mail apenas esté lista,
          no hace falta que hagas nada más.
        </p>
      </div>
    );
  }

  if (estado === "rechazado") {
    return (
      <div role="alert" className="rounded-md border border-amber/40 bg-amber-soft p-3 space-y-2">
        <p className="text-sm font-medium text-ink flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 shrink-0" />
          No pudimos validar tu identidad
        </p>
        <p className="text-xs text-muted-foreground">
          {motivo || "Didit no pudo confirmar tus datos con RENAPER."} Podés reintentar el paso.
        </p>
        <Button
          type="button"
          variant="primary"
          onClick={onVerificar}
          disabled={iniciando}
          className="h-11 w-full font-bold"
        >
          <ShieldCheck className="h-4 w-4" />
          {iniciando ? "Iniciando…" : "Reintentar verificación"}
        </Button>
      </div>
    );
  }

  return (
    <div role="status" className="rounded-md border border-amber/40 bg-amber-soft p-3 space-y-2">
      <p className="text-sm font-medium text-ink">Verificá tu identidad para continuar</p>
      <p className="text-xs text-muted-foreground">
        Alquilamos equipo de valor: necesitamos confirmar tu DNI (consulta RENAPER vía Didit). Es un
        solo paso, tarda menos de 2 minutos y guardamos solo texto — nunca la foto.
      </p>
      <Button
        type="button"
        variant="primary"
        onClick={onVerificar}
        disabled={iniciando}
        className="h-11 w-full font-bold"
      >
        <ShieldCheck className="h-4 w-4" />
        {iniciando ? "Iniciando…" : "Verificar mi identidad"}
      </Button>
    </div>
  );
}
