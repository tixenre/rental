/**
 * /admin/validacion — UI para revisar y aprobar nombres públicos uno por uno.
 *
 * Después de la clasificación + carga de specs, los nombres se generan
 * automáticamente con el builder. Pero el admin puede querer:
 *   - Aprobar el auto-generado tal cual (marca revisado=TRUE sin override).
 *   - Editarlo manualmente (guarda override + revisado=TRUE).
 *   - Volver a auto (descarta override, revisado=FALSE → reaparece).
 *
 * Una vez aprobado, el nombre NO se recalcula automáticamente al cambiar
 * specs (el admin se hizo cargo). Esto evita que mejorar specs después
 * sobrescriba lo que validó.
 */
import { createLazyFileRoute } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Check, Pencil, RotateCcw, Search, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { adminApi } from "@/lib/admin/api";
import { useDocumentTitle } from "@/lib/use-document-title";


export const Route = createLazyFileRoute("/admin/equipos/validacion")({
  component: ValidacionPage,
});


type Filtro = "all" | "pendientes" | "aprobados" | "editados";


function ValidacionPage() {
  useDocumentTitle("Validar nombres · Back Office");
  const qc = useQueryClient();
  const [filtro, setFiltro] = useState<Filtro>("pendientes");
  const [busqueda, setBusqueda] = useState("");
  const [editandoId, setEditandoId] = useState<number | null>(null);
  const [editValue, setEditValue] = useState("");

  const dataQ = useQuery({
    queryKey: ["admin", "nombres-validacion", filtro],
    queryFn: () => adminApi.listarParaValidacion(filtro),
  });

  const aprobarMut = useMutation({
    mutationFn: (args: { id: number; override?: string | null; revisado?: boolean }) =>
      adminApi.aprobarNombre(args.id, { override: args.override, revisado: args.revisado }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "nombres-validacion"] });
      qc.invalidateQueries({ queryKey: ["admin", "equipos"] });
      setEditandoId(null);
      setEditValue("");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const items = (dataQ.data?.items ?? []).filter((eq) => {
    if (!busqueda.trim()) return true;
    const q = busqueda.toLowerCase();
    return (
      (eq.nombre_publico ?? "").toLowerCase().includes(q) ||
      (eq.nombre ?? "").toLowerCase().includes(q) ||
      (eq.marca ?? "").toLowerCase().includes(q) ||
      (eq.modelo ?? "").toLowerCase().includes(q)
    );
  });
  const stats = dataQ.data?.stats;

  // Aprobar todos los visibles (en filtro Pendientes, es batch útil)
  const aprobarTodosVisibles = async () => {
    if (items.length === 0) return;
    if (!confirm(`¿Aprobar ${items.length} nombres tal cual están?`)) return;
    let ok = 0;
    for (const eq of items) {
      try {
        await adminApi.aprobarNombre(eq.id, { override: null, revisado: true });
        ok++;
      } catch (e) {
        toast.error(`Error en equipo ${eq.id}: ${e instanceof Error ? e.message : ""}`);
      }
    }
    toast.success(`${ok}/${items.length} aprobados`);
    qc.invalidateQueries({ queryKey: ["admin", "nombres-validacion"] });
    qc.invalidateQueries({ queryKey: ["admin", "equipos"] });
  };

  const empezarEdicion = (id: number, valorActual: string) => {
    setEditandoId(id);
    setEditValue(valorActual);
  };

  const guardarEdicion = (id: number) => {
    const v = editValue.trim();
    if (!v) {
      toast.error("El nombre no puede estar vacío");
      return;
    }
    aprobarMut.mutate({ id, override: v, revisado: true });
  };

  return (
    <div className="px-4 md:px-6 py-6 space-y-4 max-w-6xl mx-auto">
      <header className="flex flex-col md:flex-row md:items-end md:justify-between gap-3">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            Back-office › Equipos
          </div>
          <h1 className="font-display text-3xl text-ink">Validar nombres públicos</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Revisá y aprobá los nombres auto-generados que ve el cliente.
            Podés editarlos manualmente o dejar el automático.
          </p>
        </div>
      </header>

      {/* Stats */}
      {stats && (
        <div className="flex flex-wrap gap-2 text-sm">
          <FiltroChip
            label="Pendientes" count={stats.pendientes}
            active={filtro === "pendientes"}
            onClick={() => setFiltro("pendientes")}
            color="amber"
          />
          <FiltroChip
            label="Aprobados" count={stats.aprobados}
            active={filtro === "aprobados"}
            onClick={() => setFiltro("aprobados")}
            color="emerald"
          />
          <FiltroChip
            label="Editados" count={stats.editados}
            active={filtro === "editados"}
            onClick={() => setFiltro("editados")}
            color="blue"
          />
          <FiltroChip
            label="Todos" count={stats.total}
            active={filtro === "all"}
            onClick={() => setFiltro("all")}
            color="default"
          />
        </div>
      )}

      {/* Toolbar */}
      <div className="flex flex-col md:flex-row gap-2">
        <div className="relative md:flex-1">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            placeholder="Buscar…"
            className="pl-9"
          />
        </div>
        {filtro === "pendientes" && items.length > 0 && (
          <Button variant="outline" onClick={aprobarTodosVisibles}>
            <Check className="h-4 w-4 mr-1" /> Aprobar visibles ({items.length})
          </Button>
        )}
      </div>

      {/* Lista */}
      {dataQ.isLoading ? (
        <div className="text-center py-16 text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin mx-auto mb-2" />
          Cargando…
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground border hairline rounded-md">
          {filtro === "pendientes"
            ? "🎉 No hay nombres pendientes de aprobar."
            : "Sin resultados con estos filtros."}
        </div>
      ) : (
        <div className="rounded-lg border hairline overflow-hidden bg-background">
          <ul className="divide-y hairline">
            {items.map((eq) => {
              const estaEditando = editandoId === eq.id;
              const yaTieneOverride = !!eq.nombre_publico_override;
              return (
                <li key={eq.id} className="flex items-center gap-3 px-3 py-2.5">
                  {eq.foto_url ? (
                    <img
                      src={eq.foto_url} alt=""
                      className="h-10 w-10 rounded object-cover bg-muted/30 shrink-0"
                      onError={(e) => { (e.target as HTMLImageElement).style.opacity = "0.2"; }}
                    />
                  ) : (
                    <div className="h-10 w-10 rounded bg-muted/40 grid place-items-center text-[10px] text-muted-foreground shrink-0">
                      —
                    </div>
                  )}

                  <div className="flex-1 min-w-0">
                    {estaEditando ? (
                      <div className="flex flex-col gap-1">
                        <Input
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") { e.preventDefault(); guardarEdicion(eq.id); }
                            if (e.key === "Escape") { setEditandoId(null); setEditValue(""); }
                          }}
                          autoFocus
                          className="h-9"
                        />
                        <div className="text-[10px] text-muted-foreground">
                          Interno: <span className="font-mono">{eq.nombre}</span>
                          {" · "}Marca/Modelo: {[eq.marca, eq.modelo].filter(Boolean).join(" / ") || "—"}
                        </div>
                      </div>
                    ) : (
                      <>
                        <div className="flex items-center gap-2">
                          <span className="text-ink font-medium truncate">
                            {eq.nombre_publico ?? <span className="text-muted-foreground italic">(sin nombre)</span>}
                          </span>
                          {yaTieneOverride && (
                            <span className="text-[9px] bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded font-mono uppercase tracking-wide">
                              editado
                            </span>
                          )}
                          {eq.revisado && !yaTieneOverride && (
                            <span className="text-[9px] bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded font-mono uppercase tracking-wide">
                              aprobado
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-muted-foreground truncate">
                          <span className="font-mono">{eq.nombre}</span>
                          {(eq.marca || eq.modelo) && (
                            <span> · {[eq.marca, eq.modelo].filter(Boolean).join(" / ")}</span>
                          )}
                        </div>
                      </>
                    )}
                  </div>

                  <div className="flex gap-1 shrink-0">
                    {estaEditando ? (
                      <>
                        <Button
                          size="sm" variant="default"
                          onClick={() => guardarEdicion(eq.id)}
                          disabled={aprobarMut.isPending}
                        >
                          <Check className="h-4 w-4 mr-1" /> Guardar
                        </Button>
                        <Button
                          size="sm" variant="ghost"
                          onClick={() => { setEditandoId(null); setEditValue(""); }}
                        >
                          Cancelar
                        </Button>
                      </>
                    ) : (
                      <>
                        {!eq.revisado && (
                          <Button
                            size="sm" variant="outline"
                            onClick={() => aprobarMut.mutate({ id: eq.id, override: null, revisado: true })}
                            disabled={aprobarMut.isPending}
                            title="Aprobar tal cual"
                          >
                            <Check className="h-4 w-4 mr-1" /> Aprobar
                          </Button>
                        )}
                        <Button
                          size="sm" variant="ghost"
                          onClick={() => empezarEdicion(eq.id, eq.nombre_publico_override ?? eq.nombre_publico ?? "")}
                          title="Editar nombre manualmente"
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        {eq.revisado && (
                          <Button
                            size="sm" variant="ghost"
                            onClick={() => aprobarMut.mutate({ id: eq.id, override: null, revisado: false })}
                            disabled={aprobarMut.isPending}
                            title="Volver a auto (descarta override y se reaprueba)"
                          >
                            <RotateCcw className="h-4 w-4" />
                          </Button>
                        )}
                      </>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}


function FiltroChip({
  label, count, active, onClick, color,
}: {
  label: string; count: number; active: boolean;
  onClick: () => void;
  color: "amber" | "emerald" | "blue" | "default";
}) {
  const colors: Record<string, string> = {
    amber: active ? "border-amber bg-amber-soft text-ink" : "border-amber/30 bg-amber-soft/20",
    emerald: active ? "border-emerald-500 bg-emerald-50 text-emerald-900" : "border-emerald-500/30 bg-emerald-50/30",
    blue: active ? "border-blue-500 bg-blue-50 text-blue-900" : "border-blue-500/30 bg-blue-50/30",
    default: active ? "border-ink bg-muted text-ink" : "border-muted bg-background",
  };
  return (
    <button
      type="button"
      onClick={onClick}
      className={"rounded-md border px-3 py-1.5 text-sm hairline transition " + colors[color]}
    >
      <span className="text-muted-foreground">{label}: </span>
      <span className="font-medium">{count}</span>
    </button>
  );
}
