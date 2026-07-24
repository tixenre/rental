import { ChevronDown } from "lucide-react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/design-system/ui/collapsible";
import type { Sesion } from "@/lib/api";

function fmtFechaCorta(fecha: string): string {
  const d = new Date(fecha + "T12:00:00");
  return d.toLocaleDateString("es-AR", { weekday: "short", day: "numeric", month: "short" });
}

function Bullet({ text, index }: { text: string; index: number }) {
  return (
    <li className="flex items-start gap-3">
      <span className="shrink-0 mt-0.5 w-5 h-5 rounded-full bg-rosa text-ink text-xs font-bold grid place-items-center">
        {index + 1}
      </span>
      <span className="text-sm leading-relaxed text-muted-foreground">{text}</span>
    </li>
  );
}

export function ClaseCard({
  clase,
  numero,
  defaultOpen,
}: {
  clase: Sesion;
  numero: number;
  defaultOpen: boolean;
}) {
  const bullets = clase.descripcion
    .split("\n")
    .map((b) => b.trim())
    .filter(Boolean);
  const horaLabel = clase.hora_fin_str
    ? `${clase.hora_inicio_str} – ${clase.hora_fin_str}`
    : clase.hora_inicio_str;

  return (
    <Collapsible
      defaultOpen={defaultOpen}
      className="rounded-2xl border border-border/60 overflow-hidden"
    >
      <CollapsibleTrigger className="group flex w-full items-center gap-4 px-5 py-4 text-left hover:bg-muted/20 transition-colors">
        <span className="shrink-0 w-8 h-8 rounded-full bg-ink text-background text-sm font-bold grid place-items-center">
          {numero}
        </span>
        <div className="flex-1 min-w-0">
          <p className="font-display text-base font-bold text-ink lowercase tracking-tight truncate">
            {clase.titulo || `Clase ${numero}`}
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            {fmtFechaCorta(clase.fecha)}
            {horaLabel && ` · ${horaLabel}`}
          </p>
        </div>
        <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground/60 transition-transform duration-200 group-data-[state=open]:rotate-180" />
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="px-5 pb-5 pt-1 flex flex-col gap-4">
          {clase.portada_url && (
            <img
              src={clase.portada_url}
              alt={clase.titulo}
              loading="lazy"
              className="w-full max-h-64 rounded-xl object-cover"
            />
          )}
          {bullets.length > 0 && (
            <ul className="flex flex-col gap-3">
              {bullets.map((b, i) => (
                <Bullet key={i} text={b} index={i} />
              ))}
            </ul>
          )}
          {clase.nota && <p className="text-sm text-muted-foreground italic">{clase.nota}</p>}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
