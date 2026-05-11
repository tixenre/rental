/**
 * /admin/clasificar — Página de asignación masiva de categorías.
 *
 * Flujo:
 *   1. Al entrar, llama a clasificarBulk() que devuelve sugerencias
 *      heurísticas para todos los equipos sin categoría (o todos si
 *      el toggle "incluir asignados" está prendido).
 *   2. Cada fila muestra: foto · nombre interno · sugerencia editable
 *      (dropdown raíz + sub) · confianza · checkbox aprobar.
 *   3. "Aprobar todos los de alta confianza" preselecciona los >=0.85.
 *   4. "Aplicar (N)" manda las selecciones al backend.
 *
 * Diseño: DISEÑO_SPECS.md sección 2.3 (asignación masiva).
 */
import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Sparkles, Check, ChevronRight, AlertTriangle } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { adminApi, type CategoriaAdmin } from "@/lib/admin/api";


export const Route = createFileRoute("/admin/equipos/clasificar")({
  component: ClasificarPage,
});


type SugerenciaItem = {
  equipo_id: number;
  nombre: string;
  marca: string | null;
  modelo: string | null;
  foto_url: string | null;
  raiz: string | null;
  sub: string | null;
  raiz_id: number | null;
  sub_id: number | null;
  confianza: number;
  razon: string;
};

type EditState = {
  raiz_id: number | null;
  sub_id: number | null;
  aprobado: boolean;
};


function ClasificarPage() {
  const qc = useQueryClient();
  const [incluirAsignados, setIncluirAsignados] = useState(false);
  const [busqueda, setBusqueda] = useState("");
  const [filtroConfianza, setFiltroConfianza] = useState<"all" | "alta" | "media" | "baja">("all");

  // Estado editable por equipo (raiz_id, sub_id, aprobado).
  // Se inicializa desde las sugerencias y el admin puede editar.
  const [edits, setEdits] = useState<Record<number, EditState>>({});

  const sugerenciasQ = useQuery({
    queryKey: ["admin", "clasificar", { incluirAsignados }],
    queryFn: () => adminApi.clasificarBulk({ solo_sin_categoria: !incluirAsignados }),
  });

  const categoriasQ = useQuery({
    queryKey: ["admin", "categorias-list"],
    queryFn: () => adminApi.adminListCategorias(),
  });

  // Cuando llegan las sugerencias, inicializar el state de cada equipo.
  useEffect(() => {
    if (!sugerenciasQ.data) return;
    const init: Record<number, EditState> = {};
    for (const s of sugerenciasQ.data.items) {
      init[s.equipo_id] = {
        raiz_id: s.raiz_id ?? null,
        sub_id: s.sub_id ?? null,
        aprobado: s.confianza >= 0.85,   // alta confianza pre-aprobada
      };
    }
    setEdits(init);
  }, [sugerenciasQ.data]);

  // Helpers de categorías
  const raices = useMemo(
    () => (categoriasQ.data ?? []).filter((c) => c.parent_id == null),
    [categoriasQ.data],
  );
  const subsDe = (raiz_id: number | null) => {
    if (!raiz_id || !categoriasQ.data) return [];
    return categoriasQ.data.filter((c) => c.parent_id === raiz_id);
  };

  const aplicarMut = useMutation({
    mutationFn: (asignaciones: Array<{ equipo_id: number; categoria_ids: number[] }>) =>
      adminApi.aplicarClasificacion(asignaciones),
    onSuccess: (r) => {
      toast.success(`${r.aplicados} equipos clasificados${r.errores.length ? ` · ${r.errores.length} errores` : ""}`);
      qc.invalidateQueries({ queryKey: ["admin", "clasificar"] });
      qc.invalidateQueries({ queryKey: ["admin", "equipos"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // Filtros + búsqueda
  const itemsFiltrados = useMemo(() => {
    const all = sugerenciasQ.data?.items ?? [];
    let out = all;
    if (filtroConfianza !== "all") {
      out = out.filter((s) => {
        const c = s.confianza ?? 0;
        if (filtroConfianza === "alta") return c >= 0.85;
        if (filtroConfianza === "media") return c >= 0.7 && c < 0.85;
        if (filtroConfianza === "baja") return c < 0.7;
        return true;
      });
    }
    if (busqueda.trim()) {
      const q = busqueda.toLowerCase();
      out = out.filter((s) =>
        (s.nombre ?? "").toLowerCase().includes(q) ||
        (s.marca ?? "").toLowerCase().includes(q) ||
        (s.modelo ?? "").toLowerCase().includes(q),
      );
    }
    return out;
  }, [sugerenciasQ.data, filtroConfianza, busqueda]);

  // Stats
  const totalAprobados = Object.values(edits).filter((e) => e.aprobado).length;
  const totalConSub = Object.values(edits).filter((e) => e.aprobado && e.raiz_id != null).length;

  // Acciones bulk
  const aprobarTodosVisibles = () => {
    setEdits((prev) => {
      const next = { ...prev };
      for (const it of itemsFiltrados) {
        next[it.equipo_id] = { ...next[it.equipo_id], aprobado: true };
      }
      return next;
    });
  };
  const desaprobarTodosVisibles = () => {
    setEdits((prev) => {
      const next = { ...prev };
      for (const it of itemsFiltrados) {
        next[it.equipo_id] = { ...next[it.equipo_id], aprobado: false };
      }
      return next;
    });
  };

  const aplicar = () => {
    const asignaciones: Array<{ equipo_id: number; categoria_ids: number[] }> = [];
    for (const [eq_id, e] of Object.entries(edits)) {
      if (!e.aprobado || !e.raiz_id) continue;
      const ids = [e.raiz_id];
      if (e.sub_id) ids.push(e.sub_id);
      asignaciones.push({ equipo_id: Number(eq_id), categoria_ids: ids });
    }
    if (asignaciones.length === 0) {
      toast.info("No hay nada aprobado para aplicar");
      return;
    }
    aplicarMut.mutate(asignaciones);
  };

  // Render
  return (
    <div className="px-4 md:px-6 py-6 space-y-4 max-w-7xl mx-auto">
      <header className="flex flex-col md:flex-row md:items-end md:justify-between gap-3">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            Back-office · Rediseño
          </div>
          <h1 className="font-display text-3xl text-ink">Clasificar equipos</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Asignación masiva de categorías. La heurística pre-sugiere y vos confirmás.
            Lo aprobado se aplica al click final.
          </p>
        </div>
        <Button
          onClick={aplicar}
          disabled={aplicarMut.isPending || totalAprobados === 0}
          size="lg"
        >
          {aplicarMut.isPending ? (
            <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Aplicando…</>
          ) : (
            <>Aplicar a {totalAprobados} equipos</>
          )}
        </Button>
      </header>

      {sugerenciasQ.data && (
        <div className="flex flex-wrap gap-3 text-sm">
          <div className="rounded-md border hairline px-3 py-1.5 bg-background">
            <span className="text-muted-foreground">Total: </span>
            <span className="text-ink font-medium">{sugerenciasQ.data.total}</span>
          </div>
          <div className="rounded-md border hairline border-emerald-500/30 bg-emerald-50/30 px-3 py-1.5">
            <span className="text-muted-foreground">Alta confianza: </span>
            <span className="text-emerald-700 font-medium">{sugerenciasQ.data.alta_confianza}</span>
          </div>
          <div className="rounded-md border hairline border-amber/30 bg-amber-soft/30 px-3 py-1.5">
            <span className="text-muted-foreground">Media: </span>
            <span className="text-amber font-medium">{sugerenciasQ.data.media_confianza}</span>
          </div>
          <div className="rounded-md border hairline px-3 py-1.5 bg-background">
            <span className="text-muted-foreground">Baja: </span>
            <span className="text-ink">{sugerenciasQ.data.baja_confianza}</span>
          </div>
          {sugerenciasQ.data.sin_clasificar > 0 && (
            <div className="rounded-md border hairline border-destructive/30 bg-destructive/5 px-3 py-1.5">
              <span className="text-destructive">Sin clasificar: {sugerenciasQ.data.sin_clasificar}</span>
            </div>
          )}
        </div>
      )}

      {/* Toolbar */}
      <div className="flex flex-col md:flex-row gap-2">
        <Input
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          placeholder="Buscar por nombre, marca, modelo…"
          className="md:flex-1"
        />
        <Select value={filtroConfianza} onValueChange={(v) => setFiltroConfianza(v as never)}>
          <SelectTrigger className="md:w-48"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todas las confianzas</SelectItem>
            <SelectItem value="alta">Solo alta (&gt;= 0.85)</SelectItem>
            <SelectItem value="media">Solo media</SelectItem>
            <SelectItem value="baja">Solo baja (&lt; 0.7)</SelectItem>
          </SelectContent>
        </Select>
        <label className="flex items-center gap-1.5 text-sm rounded-md border hairline bg-background px-3 py-2 cursor-pointer">
          <input
            type="checkbox" checked={incluirAsignados}
            onChange={(e) => setIncluirAsignados(e.target.checked)}
          />
          Incluir ya asignados
        </label>
      </div>

      {/* Acciones bulk de la vista */}
      <div className="flex flex-wrap gap-2 text-sm">
        <Button variant="outline" size="sm" onClick={aprobarTodosVisibles}>
          <Check className="h-4 w-4 mr-1" /> Aprobar todos los visibles ({itemsFiltrados.length})
        </Button>
        <Button variant="ghost" size="sm" onClick={desaprobarTodosVisibles}>
          Desaprobar visibles
        </Button>
        <div className="ml-auto text-xs text-muted-foreground self-center">
          Aprobados: <span className="text-ink font-medium">{totalAprobados}</span>
          {totalAprobados !== totalConSub && (
            <span className="text-amber"> · {totalAprobados - totalConSub} sin categoría asignada</span>
          )}
        </div>
      </div>

      {/* Tabla */}
      {sugerenciasQ.isLoading ? (
        <div className="text-center py-16 text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin mx-auto mb-2" />
          Generando sugerencias…
        </div>
      ) : itemsFiltrados.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground border hairline rounded-md">
          {sugerenciasQ.data?.total === 0
            ? "🎉 Todos los equipos ya tienen categoría asignada."
            : "Sin resultados con estos filtros."}
        </div>
      ) : (
        <div className="rounded-lg border hairline overflow-hidden bg-background">
          <table className="w-full text-sm">
            <thead className="text-[10px] uppercase tracking-wide text-muted-foreground border-b hairline bg-muted/30">
              <tr>
                <th className="text-left px-3 py-2 w-10">✓</th>
                <th className="text-left px-3 py-2 w-12"></th>
                <th className="text-left px-3 py-2">Equipo</th>
                <th className="text-left px-3 py-2 w-44">Raíz</th>
                <th className="text-left px-3 py-2 w-52">Sub-categoría</th>
                <th className="text-left px-3 py-2 w-32">Razón</th>
              </tr>
            </thead>
            <tbody>
              {itemsFiltrados.map((s) => {
                const e = edits[s.equipo_id];
                if (!e) return null;
                const subs = subsDe(e.raiz_id);
                const confColor =
                  s.confianza >= 0.85 ? "text-emerald-700" :
                  s.confianza >= 0.7 ? "text-amber" :
                  s.confianza > 0 ? "text-muted-foreground" : "text-destructive";
                return (
                  <tr key={s.equipo_id} className={"border-t hairline " + (e.aprobado ? "bg-emerald-50/20" : "")}>
                    <td className="px-3 py-2 align-top">
                      <input
                        type="checkbox" checked={e.aprobado}
                        onChange={(ev) => setEdits((prev) => ({
                          ...prev, [s.equipo_id]: { ...prev[s.equipo_id], aprobado: ev.target.checked },
                        }))}
                        className="cursor-pointer"
                      />
                    </td>
                    <td className="px-3 py-2 align-top">
                      {s.foto_url ? (
                        <img
                          src={s.foto_url} alt=""
                          className="h-9 w-9 rounded object-cover bg-muted/30"
                          onError={(ev) => { (ev.target as HTMLImageElement).style.opacity = "0.2"; }}
                        />
                      ) : (
                        <div className="h-9 w-9 rounded bg-muted/40 grid place-items-center text-[10px] text-muted-foreground">
                          —
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-2 align-top">
                      <div className="font-medium text-ink">{s.nombre}</div>
                      <div className="text-[11px] text-muted-foreground">
                        {[s.marca, s.modelo].filter(Boolean).join(" / ") || "—"}
                      </div>
                    </td>
                    <td className="px-3 py-2 align-top">
                      <Select
                        value={e.raiz_id ? String(e.raiz_id) : "__none"}
                        onValueChange={(v) => setEdits((prev) => ({
                          ...prev,
                          [s.equipo_id]: {
                            raiz_id: v === "__none" ? null : Number(v),
                            sub_id: null,   // resetear sub al cambiar raíz
                            aprobado: prev[s.equipo_id].aprobado,
                          },
                        }))}
                      >
                        <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="__none">— ninguna —</SelectItem>
                          {raices.map((r) => (
                            <SelectItem key={r.id} value={String(r.id)}>{r.nombre}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </td>
                    <td className="px-3 py-2 align-top">
                      <Select
                        value={e.sub_id ? String(e.sub_id) : "__none"}
                        onValueChange={(v) => setEdits((prev) => ({
                          ...prev,
                          [s.equipo_id]: { ...prev[s.equipo_id], sub_id: v === "__none" ? null : Number(v) },
                        }))}
                        disabled={subs.length === 0}
                      >
                        <SelectTrigger className="h-8 text-xs"><SelectValue placeholder={subs.length === 0 ? "(elegí raíz)" : "—"} /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="__none">— ninguna —</SelectItem>
                          {subs.map((c) => (
                            <SelectItem key={c.id} value={String(c.id)}>{c.nombre}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </td>
                    <td className="px-3 py-2 align-top">
                      <div className="text-[11px] text-muted-foreground">{s.razon}</div>
                      <Badge variant="outline" className={"text-[9px] " + confColor}>
                        {s.confianza > 0 ? `${(s.confianza * 100).toFixed(0)}%` : "sin match"}
                      </Badge>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
