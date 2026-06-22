import { ShieldCheck } from "lucide-react";
import { Button } from "@/design-system/ui/button";

export function VerificacionRequeridaPanel({
  onVerificar,
  iniciando,
}: {
  onVerificar: () => void;
  iniciando?: boolean;
}) {
  return (
    <div className="rounded-md border border-amber/40 bg-amber-soft p-3 space-y-2">
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
