import { createLazyFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  Sparkles,
  Hash,
  DollarSign,
  Camera,
  FileText,
  Tag,
  Folder,
  AlertCircle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { adminApi, type CalidadInventario } from "@/lib/admin/api";

export const Route = createLazyFileRoute("/admin/equipos/calidad")({
  component: CalidadPage,
});

function CalidadPage() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["admin", "inventario", "calidad"],
    queryFn: () => adminApi.getCalidadInventario(),
    staleTime: 60_000,
  });

  return (
    <div className="px-4 md:px-8 py-6 md:py-10 max-w-3xl mx-auto">
      <header className="mb-8">
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Back-office › Equipos
        </div>
        <h1 className="font-display text-3xl md:text-4xl text-ink flex items-center gap-2">
          <Sparkles className="h-7 w-7 text-amber" />
          Calidad del inventario
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Qué equipos tienen datos faltantes. Solo lectura — los CTAs para
          completar llegan en una segunda iteración (#350).
        </p>
      </header>

      {isLoading && <Skeleton />}

      {isError && (
        <div className="rounded-xl border border-destructive/40 bg-destructive/5 px-4 py-6 text-sm text-destructive">
          <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.25em] mb-2">
            <AlertCircle className="h-3.5 w-3.5" /> Error
          </div>
          <div>{(error as Error)?.message ?? "No se pudo cargar la calidad del inventario."}</div>
        </div>
      )}

      {data && <CalidadView data={data} />}
    </div>
  );
}

function CalidadView({ data }: { data: CalidadInventario }) {
  const filas: Array<{ key: keyof CalidadInventario["faltantes"]; label: string; icon: LucideIcon }> = [
    { key: "foto",             label: "sin foto principal",           icon: Camera },
    { key: "categoria",        label: "sin categoría asignada",       icon: Folder },
    { key: "nombre_publico",   label: "sin nombre público",           icon: Tag },
    { key: "descripcion",      label: "sin descripción extendida",    icon: FileText },
    { key: "serie",            label: "sin número de serie",          icon: Hash },
    { key: "valor_reposicion", label: "sin valor de reposición",      icon: DollarSign },
  ];

  return (
    <>
      <section className="rounded-2xl border hairline bg-surface p-6 mb-6">
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground mb-2">
          Inventario
        </div>
        <div className="flex items-baseline gap-3 mb-4">
          <div className="font-display text-4xl text-ink tabular">{data.total}</div>
          <div className="text-sm text-muted-foreground">equipos activos</div>
        </div>
        <ProgressBar pct={data.completos_pct} />
        <div className="mt-2 flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
          <span className="tabular text-ink">{data.completos_pct}%</span>
          <span>completos</span>
        </div>
      </section>

      <section className="rounded-2xl border hairline bg-surface">
        <header className="px-5 pt-4 pb-3 border-b hairline font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Faltantes por campo
        </header>
        <ul>
          {filas
            .sort((a, b) => data.faltantes[b.key] - data.faltantes[a.key])
            .map(({ key, label, icon: Icon }) => {
              const n = data.faltantes[key];
              if (n === 0) return null;
              const pct = data.total === 0 ? 0 : Math.round((n / data.total) * 100);
              return (
                <li
                  key={key}
                  className="flex items-center gap-3 px-5 py-3 border-b hairline last:border-b-0"
                >
                  <div className="grid h-8 w-8 place-items-center rounded-full bg-amber-soft text-ink/80">
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-ink">
                      <span className="font-display text-base tabular text-ink">{n}</span>{" "}
                      <span className="text-muted-foreground">{label}</span>
                    </div>
                    <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
                      {pct}% del inventario
                    </div>
                  </div>
                  <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/60">
                    pendiente
                  </span>
                </li>
              );
            })}
          {filas.every(({ key }) => data.faltantes[key] === 0) && (
            <li className="px-5 py-8 text-center text-sm text-muted-foreground">
              ✓ Inventario completo — sin campos faltantes.
            </li>
          )}
        </ul>
      </section>
    </>
  );
}

function ProgressBar({ pct }: { pct: number }) {
  const safe = Math.max(0, Math.min(100, pct));
  return (
    <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
      <div
        className="h-full bg-amber transition-all"
        style={{ width: `${safe}%` }}
      />
    </div>
  );
}

function Skeleton() {
  return (
    <>
      <div className="rounded-2xl border hairline bg-surface p-6 mb-6 animate-pulse">
        <div className="h-3 w-24 rounded bg-muted mb-3" />
        <div className="h-8 w-32 rounded bg-muted mb-4" />
        <div className="h-2 w-full rounded-full bg-muted" />
      </div>
      <div className="rounded-2xl border hairline bg-surface animate-pulse">
        <div className="h-10 border-b hairline" />
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-16 border-b hairline last:border-b-0" />
        ))}
      </div>
    </>
  );
}
