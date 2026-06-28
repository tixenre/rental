import { createLazyFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  Hash,
  DollarSign,
  Camera,
  FileText,
  Tag,
  Folder,
  ArrowRight,
  Lightbulb,
  Loader2,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/design-system/ui/button";
import {
  adminApi,
  type CalidadInventario,
  type FaltaField,
  type Sugerencia,
} from "@/lib/admin/api";
import { AdminPage } from "@/components/admin/AdminPage";
import { QueryState } from "@/components/admin/QueryState";
import { useDocumentTitle } from "@/lib/use-document-title";

export const Route = createLazyFileRoute("/admin/equipos/calidad")({
  component: CalidadPage,
});

function CalidadPage() {
  useDocumentTitle("Calidad · Back Office");
  const calidadQ = useQuery({
    queryKey: ["admin", "inventario", "calidad"],
    queryFn: () => adminApi.getCalidadInventario(),
    staleTime: 60_000,
  });

  return (
    <AdminPage
      title="Calidad del inventario"
      maxW="max-w-3xl"
      description="Qué equipos tienen datos faltantes. Solo lectura — los CTAs para completar llegan en una segunda iteración (#350)."
    >
      <QueryState
        query={calidadQ}
        skeleton={<Skeleton />}
        errorTitle="No se pudo cargar la calidad del inventario"
      >
        {(data) => <CalidadView data={data} />}
      </QueryState>

      <SugerenciasSection />
    </AdminPage>
  );
}

function SugerenciasSection() {
  const qc = useQueryClient();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["admin", "inventario", "sugerencias"],
    queryFn: () => adminApi.getSugerenciasInventario(),
    staleTime: 60_000,
  });
  const [busy, setBusy] = useState<string | null>(null);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin", "inventario", "sugerencias"] });
    qc.invalidateQueries({ queryKey: ["admin", "inventario", "calidad"] });
    qc.invalidateQueries({ queryKey: ["admin", "equipos"] });
    qc.invalidateQueries({ queryKey: ["admin", "marcas-list"] });
  };

  const aplicar = useMutation({
    mutationFn: ({ tipo, ref }: { tipo: Sugerencia["tipo"]; ref: string }) =>
      adminApi.aplicarSugerencia(tipo, ref),
    onMutate: ({ tipo, ref }) => setBusy(`apply:${tipo}:${ref}`),
    onSuccess: (resp) => {
      toast.success(resp.message);
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
    onSettled: () => setBusy(null),
  });

  const ignorar = useMutation({
    mutationFn: ({ tipo, ref }: { tipo: Sugerencia["tipo"]; ref: string }) =>
      adminApi.ignorarSugerencia(tipo, ref),
    onMutate: ({ tipo, ref }) => setBusy(`ignore:${tipo}:${ref}`),
    onSuccess: () => {
      toast.success("Sugerencia descartada");
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
    onSettled: () => setBusy(null),
  });

  if (isLoading || isError) return null;
  if (!data || data.items.length === 0) return null;

  return (
    <section className="mt-8 rounded-2xl border hairline bg-surface">
      <header className="flex items-center gap-2 px-5 pt-4 pb-3 border-b hairline">
        <Lightbulb className="h-4 w-4 text-ink" />
        <span className="t-eyebrow">Sugerencias del sistema · {data.total}</span>
      </header>
      <ul className="divide-y hairline">
        {data.items.map((s, i) => {
          const key = `${s.tipo}:${s.ref}`;
          const isApplying = busy === `apply:${key}`;
          const isIgnoring = busy === `ignore:${key}`;
          return (
            <li key={`${key}:${i}`} className="px-5 py-4 space-y-2">
              <div className="flex items-start gap-3">
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-ink">{s.titulo}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">{s.detalle}</div>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={isIgnoring || isApplying}
                    onClick={() => ignorar.mutate({ tipo: s.tipo, ref: s.ref })}
                    title="Descartar — no volverá a aparecer"
                  >
                    {isIgnoring ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Ignorar"}
                  </Button>
                  {s.equipo_id && (
                    <Button
                      asChild
                      size="sm"
                      variant="outline"
                      title="Abrir el equipo para revisar manualmente"
                    >
                      <Link to="/admin/equipos" search={{ q: String(s.equipo_id) }}>
                        Editar →
                      </Link>
                    </Button>
                  )}
                  <Button
                    size="sm"
                    disabled={isApplying || isIgnoring}
                    onClick={() => aplicar.mutate({ tipo: s.tipo, ref: s.ref })}
                  >
                    {isApplying ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" /> Aplicando…
                      </>
                    ) : (
                      s.accion_label
                    )}
                  </Button>
                </div>
              </div>
              {s.marcas && s.marcas.length > 0 && (
                <ul className="ml-1 mt-2 text-xs text-muted-foreground space-y-0.5">
                  {s.marcas.map((m, idx) => (
                    <li key={m.id} className="font-mono tabular">
                      {idx === 0 ? "→ " : "   "}
                      <span className={idx === 0 ? "text-ink font-medium" : ""}>{m.nombre}</span>
                      <span className="opacity-70">
                        {" "}
                        · id={m.id} · {m.equipos} equipos · {m.cant_pedidos} pedidos
                      </span>
                      {idx === 0 && <span className="ml-2 text-ink">(canonical)</span>}
                    </li>
                  ))}
                </ul>
              )}
              {s.equipos && s.equipos.length > 0 && (
                <details className="text-xs text-muted-foreground">
                  <summary className="cursor-pointer hover:text-ink">
                    Ver equipos ({s.equipos.length})
                  </summary>
                  <ul className="ml-3 mt-1 space-y-0.5">
                    {s.equipos.slice(0, 10).map((e) => (
                      <li key={e.id} className="font-mono tabular">
                        {e.marca} {e.nombre} · ${e.precio_jornada.toLocaleString("es-AR")}/jornada
                      </li>
                    ))}
                    {s.equipos.length > 10 && (
                      <li className="opacity-60">… y {s.equipos.length - 10} más</li>
                    )}
                  </ul>
                </details>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function CalidadView({ data }: { data: CalidadInventario }) {
  const filas: Array<{ key: FaltaField; label: string; icon: LucideIcon }> = [
    { key: "foto", label: "sin foto principal", icon: Camera },
    { key: "categoria", label: "sin categoría asignada", icon: Folder },
    { key: "nombre_publico", label: "sin nombre público", icon: Tag },
    { key: "descripcion", label: "sin descripción extendida", icon: FileText },
    { key: "serie", label: "sin número de serie", icon: Hash },
    { key: "valor_reposicion", label: "sin valor de reposición", icon: DollarSign },
  ];

  return (
    <>
      <section className="rounded-2xl border hairline bg-surface p-6 mb-6">
        <div className="t-eyebrow mb-2">Inventario</div>
        <div className="flex items-baseline gap-3 mb-4">
          <div className="font-display text-4xl text-ink tabular">{data.total}</div>
          <div className="text-sm text-muted-foreground">equipos activos</div>
        </div>
        <ProgressBar pct={data.completos_pct} />
        <div className="mt-2 flex items-center gap-2 t-eyebrow">
          <span className="tabular text-ink">{data.completos_pct}%</span>
          <span>completos</span>
        </div>
      </section>

      <section className="rounded-2xl border hairline bg-surface">
        <header className="px-5 pt-4 pb-3 border-b hairline t-eyebrow">Faltantes por campo</header>
        <ul>
          {filas
            .sort((a, b) => data.faltantes[b.key] - data.faltantes[a.key])
            .map(({ key, label, icon: Icon }) => {
              const n = data.faltantes[key];
              if (n === 0) return null;
              const pct = data.total === 0 ? 0 : Math.round((n / data.total) * 100);
              return (
                <li key={key}>
                  <Link
                    to="/admin/equipos"
                    search={{ falta: key }}
                    className="group flex items-center gap-3 px-5 py-3 border-b hairline last:border-b-0 transition hover:bg-amber-soft/50"
                  >
                    <div className="grid h-8 w-8 place-items-center rounded-full bg-amber-soft text-ink/80 transition group-hover:bg-amber group-hover:text-ink">
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-ink">
                        <span className="font-display text-base tabular text-ink">{n}</span>{" "}
                        <span className="text-muted-foreground">{label}</span>
                      </div>
                      <div className="t-eyebrow">{pct}% del inventario</div>
                    </div>
                    <span className="t-eyebrow inline-flex items-center gap-1 transition group-hover:text-ink">
                      Completar
                      <ArrowRight className="h-3 w-3 transition group-hover:translate-x-0.5" />
                    </span>
                  </Link>
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
      <div className="h-full bg-amber transition-all" style={{ width: `${safe}%` }} />
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
