import { ShieldCheck } from "lucide-react";

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
      <button
        type="button"
        onClick={onVerificar}
        disabled={iniciando}
        className="flex h-11 w-full items-center justify-center gap-2 rounded-md bg-ink text-sm font-bold text-amber transition hover:bg-amber hover:text-ink disabled:opacity-50"
      >
        <ShieldCheck className="h-4 w-4" />
        {iniciando ? "Iniciando…" : "Verificar mi identidad"}
      </button>
    </div>
  );
}
