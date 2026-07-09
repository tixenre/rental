/**
 * EquipoPreviewAside — preview sticky del costado (foto + KPIs).
 *
 * Extraído verbatim de `EquipoFormDialogV2.tsx` (split de god-module, Frente E
 * del skill `mantenimiento`, F2a #1263). Puramente de lectura — no dispara
 * ningún cambio, así que recibe los valores ya resueltos en vez de `form`.
 */
import { Image as ImageIcon } from "lucide-react";
import { Monto, PrecioUnidad } from "@/components/admin/Monto";
import type { FormValues } from "./equipo-form-schema";

function kpiFmt(n: unknown) {
  return typeof n === "number" && !Number.isNaN(n) ? n.toLocaleString("es-AR") : "—";
}

export function EquipoPreviewAside({
  fotoActual,
  nombre,
  nombrePublico,
  precioJornada,
  roiPct,
  valorReposicion,
}: {
  fotoActual: string | undefined;
  nombre: FormValues["nombre"];
  nombrePublico: string;
  precioJornada: FormValues["precio_jornada"];
  roiPct: FormValues["roi_pct"];
  valorReposicion: FormValues["valor_reposicion"];
}) {
  return (
    <aside className="space-y-3 lg:sticky lg:top-6">
      <div className="rounded-lg border hairline bg-card overflow-hidden">
        <div className="aspect-square bg-white grid place-items-center p-4">
          {fotoActual ? (
            <img
              loading="lazy"
              decoding="async"
              src={fotoActual}
              alt=""
              className="max-h-full max-w-full object-contain"
            />
          ) : (
            <ImageIcon className="h-10 w-10 text-muted-foreground/30" />
          )}
        </div>
        <div className="p-3 border-t hairline">
          <div className="font-medium text-ink text-sm leading-tight">
            {nombre || "Equipo sin nombre"}
          </div>
          {nombrePublico && (
            <div className="text-xs text-muted-foreground italic mt-0.5">{nombrePublico}</div>
          )}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-lg border hairline bg-card px-3 py-2.5">
          <div className="t-eyebrow">$ / jornada</div>
          <div className="font-display text-xl font-black text-ink tabular-nums mt-0.5">
            <PrecioUnidad value={precioJornada} />
          </div>
        </div>
        <div className="rounded-lg border hairline bg-card px-3 py-2.5">
          <div className="t-eyebrow">% día</div>
          <div className="font-display text-xl font-black text-ink tabular-nums mt-0.5">
            {kpiFmt(roiPct)}%
          </div>
        </div>
        <div className="rounded-lg border hairline bg-card px-3 py-2.5 col-span-2">
          <div className="t-eyebrow">Valor reposición</div>
          <div className="font-display text-xl font-black text-ink tabular-nums mt-0.5">
            <Monto value={valorReposicion} moneda="USD" />
          </div>
        </div>
      </div>
    </aside>
  );
}
