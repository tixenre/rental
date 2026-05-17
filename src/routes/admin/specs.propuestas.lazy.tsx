import { createLazyFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import {
  Sparkles, Check, X, Loader2, ChevronDown, ChevronRight, ListPlus, Plus, GitMerge, Link2,
  CheckSquare, Square,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

import {
  adminApi,
  type PropuestaPendiente,
  type PropuestaTipo,
} from "@/lib/admin/api";
import { useDocumentTitle } from "@/lib/use-document-title";

export const Route = createLazyFileRoute("/admin/specs/propuestas")({
  component: PropuestasPage,
});

/** Contenido reusable para embeber en la pantalla unificada Gear Compat. */
export function PropuestasContent() {
  return <PropuestasPage embedded />;
}

const TIPO_META: Record<PropuestaTipo, { label: string; icon: typeof Check; color: string }> = {
  enum_option: { label: "Nueva opción de enum", icon: ListPlus, color: "text-emerald-700" },
  spec_nueva: { label: "Spec nueva", icon: Plus, color: "text-amber-700" },
  merge_specs: { label: "Consolidar specs", icon: GitMerge, color: "text-blue-700" },
  assign_spec: { label: "Asignar spec existente a categoría", icon: Link2, color: "text-purple-700" },
};

type Estado = "pendientes" | "aplicadas" | "descartadas" | "todas";

function PropuestasPage({ embedded = false }: { embedded?: boolean } = {}) {
  useDocumentTitle("Propuestas IA · Back Office");
  const qc = useQueryClient();
  const [estado, setEstado] = useState<Estado>("pendientes");
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [minConfianza, setMinConfianza] = useState<string>("none");

  const listQ = useQuery({
    queryKey: ["admin", "spec-propuestas", estado],
    queryFn: () => adminApi.listarPropuestas(estado),
    staleTime: 10_000,
  });

  const aplicarMut = useMutation({
    mutationFn: (id: number) => adminApi.aplicarPropuesta(id),
    onSuccess: () => {
      toast.success("Propuesta aplicada");
      qc.invalidateQueries({ queryKey: ["admin", "spec-propuestas"] });
      qc.invalidateQueries({ queryKey: ["admin", "spec-definitions"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const descartarMut = useMutation({
    mutationFn: (id: number) => adminApi.descartarPropuesta(id),
    onSuccess: () => {
      toast.success("Propuesta descartada");
      qc.invalidateQueries({ queryKey: ["admin", "spec-propuestas"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const bulkMut = useMutation({
    mutationFn: (input: { ids: number[]; accion: "apply" | "discard"; min_confianza?: number }) =>
      adminApi.bulkPropuestas(input),
    onSuccess: (data) => {
      const accionLabel = data.failed.length === 0 ? "Procesadas" : "Parcial";
      const detalle = data.failed.length > 0
        ? ` (${data.ok_count} ok, ${data.failed.length} fallaron)`
        : ` (${data.ok_count})`;
      const skipped = data.skipped_by_confianza > 0
        ? `, ${data.skipped_by_confianza} omitidas por confianza`
        : "";
      toast.success(`${accionLabel}${detalle}${skipped}`);
      setSelectedIds(new Set());
      qc.invalidateQueries({ queryKey: ["admin", "spec-propuestas"] });
      qc.invalidateQueries({ queryKey: ["admin", "spec-definitions"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const items = listQ.data?.items ?? [];
  const grupos: Record<PropuestaTipo, PropuestaPendiente[]> = {
    enum_option: [],
    spec_nueva: [],
    merge_specs: [],
    assign_spec: [],
  };
  for (const p of items) grupos[p.tipo].push(p);

  // Propuestas seleccionables: pendientes que aún no fueron procesadas.
  const seleccionables = items.filter((p) => !p.aplicado_at && !p.descartado_at);
  const selectableIds = new Set(seleccionables.map((p) => p.id));
  const allSelected = seleccionables.length > 0 && seleccionables.every((p) => selectedIds.has(p.id));
  const someSelected = selectedIds.size > 0;

  function toggleSelect(id: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(selectableIds));
    }
  }

  function runBulk(accion: "apply" | "discard") {
    const ids = Array.from(selectedIds).filter((id) => selectableIds.has(id));
    if (ids.length === 0) return;
    const conf = minConfianza === "none" ? undefined : Number(minConfianza);
    bulkMut.mutate({ ids, accion, min_confianza: conf });
  }

  return (
    <div className={embedded ? "space-y-6" : "px-4 md:px-6 py-6 space-y-6 max-w-5xl mx-auto"}>
      <header className="flex items-end justify-between gap-3 flex-wrap">
        <div>
          {!embedded && (
            <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
              Back-office › Specs
            </div>
          )}
          <h1 className={embedded
            ? "font-display text-xl text-ink flex items-center gap-2"
            : "font-display text-3xl text-ink flex items-center gap-2"}>
            <Sparkles className={embedded ? "h-5 w-5 text-amber" : "h-6 w-6 text-amber"} />
            Propuestas IA
          </h1>
          <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
            Cambios al catálogo de specs sugeridos por el skill
            <code className="font-mono mx-1">gear-compatibility</code>.
            Revisá cada uno antes de aplicar: las opciones de enum y specs
            nuevas afectan el front público (cards/filtros) y a todos los
            equipos de las categorías asignadas.
          </p>
        </div>
        <Select value={estado} onValueChange={(v) => setEstado(v as Estado)}>
          <SelectTrigger className="w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="pendientes">Pendientes</SelectItem>
            <SelectItem value="aplicadas">Aplicadas</SelectItem>
            <SelectItem value="descartadas">Descartadas</SelectItem>
            <SelectItem value="todas">Todas</SelectItem>
          </SelectContent>
        </Select>
      </header>

      {/* Toolbar bulk: solo visible cuando estamos viendo pendientes y hay
          algo seleccionable. Permite aplicar/descartar varias propuestas a
          la vez, opcionalmente filtrando por confianza mínima. */}
      {estado === "pendientes" && seleccionables.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded-md border hairline bg-muted/10 px-3 py-2 text-sm">
          <button
            type="button"
            onClick={toggleSelectAll}
            className="inline-flex items-center gap-1.5 text-ink hover:text-amber"
          >
            {allSelected
              ? <CheckSquare className="h-4 w-4 text-amber" />
              : <Square className="h-4 w-4 text-muted-foreground" />}
            <span className="text-xs">
              {allSelected ? "Deseleccionar todas" : `Seleccionar todas (${seleccionables.length})`}
            </span>
          </button>

          <span className="text-muted-foreground">·</span>

          <div className="flex items-center gap-1.5">
            <span className="text-xs text-muted-foreground">Mín. confianza</span>
            <Select value={minConfianza} onValueChange={setMinConfianza}>
              <SelectTrigger className="h-7 w-24 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">Cualquiera</SelectItem>
                <SelectItem value="0.5">≥ 50%</SelectItem>
                <SelectItem value="0.7">≥ 70%</SelectItem>
                <SelectItem value="0.8">≥ 80%</SelectItem>
                <SelectItem value="0.9">≥ 90%</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex-1" />

          {someSelected && (
            <Badge variant="outline" className="text-[10px]">
              {selectedIds.size} seleccionadas
            </Badge>
          )}

          <Button
            size="sm" variant="outline"
            onClick={() => runBulk("discard")}
            disabled={!someSelected || bulkMut.isPending}
            className="h-7 px-2"
          >
            <X className="h-3 w-3 mr-1" />
            Descartar
          </Button>
          <Button
            size="sm"
            onClick={() => runBulk("apply")}
            disabled={!someSelected || bulkMut.isPending}
            className="h-7 px-2"
          >
            {bulkMut.isPending
              ? <Loader2 className="h-3 w-3 mr-1 animate-spin" />
              : <Check className="h-3 w-3 mr-1" />}
            Aplicar
          </Button>
        </div>
      )}

      {listQ.isLoading && (
        <div className="rounded-md border hairline px-4 py-6 text-center text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin mx-auto mb-1" />
          Cargando…
        </div>
      )}

      {!listQ.isLoading && items.length === 0 && (
        <div className="rounded-md border hairline border-dashed p-6 text-center text-sm text-muted-foreground">
          {estado === "pendientes" ? (
            <>
              No hay propuestas pendientes. Ejecutá
              <code className="font-mono mx-1">/gear-compat new</code>
              o <code className="font-mono">/gear-compat all</code> para
              que el skill genere propuestas.
            </>
          ) : (
            <>No hay propuestas en estado "{estado}".</>
          )}
        </div>
      )}

      {(["assign_spec", "enum_option", "spec_nueva", "merge_specs"] as PropuestaTipo[]).map((tipo) => {
        const list = grupos[tipo];
        if (list.length === 0) return null;
        const meta = TIPO_META[tipo];
        const Icon = meta.icon;
        return (
          <section key={tipo} className="space-y-2">
            <header className={"flex items-center gap-2 text-sm font-medium " + meta.color}>
              <Icon className="h-4 w-4" />
              {meta.label} ({list.length})
            </header>
            <div className="rounded-md border hairline divide-y hairline overflow-hidden">
              {list.map((p) => (
                <PropuestaRow
                  key={p.id}
                  propuesta={p}
                  selected={selectedIds.has(p.id)}
                  selectable={estado === "pendientes" && selectableIds.has(p.id)}
                  onToggleSelect={() => toggleSelect(p.id)}
                  onAplicar={() => aplicarMut.mutate(p.id)}
                  onDescartar={() => descartarMut.mutate(p.id)}
                  busy={aplicarMut.isPending || descartarMut.isPending || bulkMut.isPending}
                />
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}

function PropuestaRow({
  propuesta, selected, selectable, onToggleSelect, onAplicar, onDescartar, busy,
}: {
  propuesta: PropuestaPendiente;
  selected: boolean;
  selectable: boolean;
  onToggleSelect: () => void;
  onAplicar: () => void;
  onDescartar: () => void;
  busy: boolean;
}) {
  const [open, setOpen] = useState(false);
  const yaAplicada = !!propuesta.aplicado_at;
  const yaDescartada = !!propuesta.descartado_at;
  const finalizada = yaAplicada || yaDescartada;

  return (
    <div className={`px-3 py-2 text-sm hover:bg-muted/20 ${selected ? "bg-amber-soft/20" : ""}`}>
      <div className="flex items-start gap-2">
        {selectable && (
          <button
            type="button"
            onClick={onToggleSelect}
            className="mt-0.5 text-muted-foreground hover:text-amber"
            aria-label={selected ? "Deseleccionar" : "Seleccionar"}
          >
            {selected
              ? <CheckSquare className="h-4 w-4 text-amber" />
              : <Square className="h-4 w-4" />}
          </button>
        )}
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="mt-0.5 text-muted-foreground hover:text-ink"
          aria-label={open ? "Cerrar" : "Abrir"}
        >
          {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </button>
        <div className="flex-1 min-w-0">
          <PropuestaResumen propuesta={propuesta} />
          <div className="flex items-center gap-2 mt-0.5 text-[10px] text-muted-foreground">
            <span>{propuesta.origen ?? "skill"}</span>
            {propuesta.confianza != null && (
              <Badge variant="outline" className="text-[9px]">
                conf {Math.round(propuesta.confianza * 100)}%
              </Badge>
            )}
            <span>·</span>
            <span>{new Date(propuesta.created_at).toLocaleString()}</span>
            {yaAplicada && (
              <Badge className="bg-emerald-100 text-emerald-800 text-[9px]">aplicada</Badge>
            )}
            {yaDescartada && (
              <Badge variant="outline" className="text-[9px]">descartada</Badge>
            )}
          </div>
        </div>
        {!finalizada && (
          <div className="flex gap-1 shrink-0">
            <Button
              size="sm" variant="outline"
              onClick={onDescartar} disabled={busy}
              className="h-7 px-2"
            >
              <X className="h-3 w-3 mr-1" /> Descartar
            </Button>
            <Button
              size="sm"
              onClick={onAplicar} disabled={busy}
              className="h-7 px-2"
            >
              <Check className="h-3 w-3 mr-1" /> Aplicar
            </Button>
          </div>
        )}
      </div>
      {open && (
        <pre className="mt-2 ml-6 max-h-64 overflow-auto rounded bg-muted/40 p-2 text-[10px] font-mono">
          {JSON.stringify(propuesta.payload, null, 2)}
        </pre>
      )}
    </div>
  );
}

function PropuestaResumen({ propuesta }: { propuesta: PropuestaPendiente }) {
  const p = propuesta.payload as Record<string, unknown>;
  if (propuesta.tipo === "enum_option") {
    const opts = (p.options as string[] | undefined) ?? [];
    return (
      <div>
        <span className="text-ink">Agregar opciones a spec </span>
        <code className="font-mono text-[11px]">#{String(p.spec_def_id ?? "?")}</code>:{" "}
        <span className="text-muted-foreground">{opts.map((o) => `"${o}"`).join(", ")}</span>
      </div>
    );
  }
  if (propuesta.tipo === "spec_nueva") {
    const razon = typeof p.razon === "string" ? p.razon : null;
    return (
      <div>
        <span className="text-ink">Crear spec </span>
        <code className="font-mono text-[11px]">{String(p.spec_key ?? "?")}</code>{" "}
        <span className="text-muted-foreground">
          ({String(p.tipo ?? "?")}{p.unidad ? `, ${String(p.unidad)}` : ""})
        </span>
        {razon && (
          <span className="text-[10px] text-muted-foreground"> — {razon}</span>
        )}
      </div>
    );
  }
  if (propuesta.tipo === "merge_specs") {
    const mergeIds = (p.merge_spec_def_ids as number[] | undefined) ?? [];
    return (
      <div>
        <span className="text-ink">Consolidar </span>
        {mergeIds.map((id) => (
          <code key={id} className="font-mono text-[11px] mr-1">#{id}</code>
        ))}
        <span className="text-muted-foreground">→ </span>
        <code className="font-mono text-[11px]">#{String(p.keep_spec_def_id ?? "?")}</code>
      </div>
    );
  }
  if (propuesta.tipo === "assign_spec") {
    const valor = typeof p.valor_sugerido === "string" ? p.valor_sugerido : null;
    const equipoId = typeof p.source_equipo_id === "number" ? p.source_equipo_id : null;
    return (
      <div>
        <span className="text-ink">Asignar </span>
        <code className="font-mono text-[11px]">{String(p.spec_key ?? p.spec_def_id ?? "?")}</code>
        <span className="text-muted-foreground"> a categoría </span>
        <code className="font-mono text-[11px]">#{String(p.categoria_id ?? "?")}</code>
        {valor && (
          <span className="text-[10px] text-muted-foreground"> · valor detectado: <code className="font-mono">"{valor}"</code></span>
        )}
        {equipoId && (
          <span className="text-[10px] text-muted-foreground"> · desde equipo #{equipoId}</span>
        )}
      </div>
    );
  }
  return <span className="text-muted-foreground">Propuesta desconocida</span>;
}
