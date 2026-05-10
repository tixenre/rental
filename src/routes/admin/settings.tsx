import { useEffect, useMemo, useRef, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDown, ArrowUp, Upload, Wrench, AlertTriangle, Loader2,
  Plus, Trash2, ChevronRight, ChevronDown, Sparkles, GripVertical, X,
} from "lucide-react";
import { toast } from "sonner";
import {
  DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors,
  DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove, SortableContext, sortableKeyboardCoordinates, verticalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";

import { adminApi, type ImportCsvResp, type CategoriaAdmin, type EtiquetaAdmin, type ClasificarResult, type MarcaAdmin } from "@/lib/admin/api";
import { SpecTemplatesSection } from "@/components/admin/specs/SpecTemplatesSection";

export const Route = createFileRoute("/admin/settings")({
  component: SettingsPage,
});

type Kind = "equipos" | "clientes" | "alquileres";

function SettingsPage() {
  const [results, setResults] = useState<Record<Kind, ImportCsvResp | null>>({
    equipos: null, clientes: null, alquileres: null,
  });
  const [confirmReset, setConfirmReset] = useState(false);

  const importMut = useMutation({
    mutationFn: ({ kind, file }: { kind: Kind; file: File }) =>
      adminApi.importCsv(kind, file),
    onSuccess: (data, { kind }) => {
      setResults((prev) => ({ ...prev, [kind]: data }));
      const ok = data.success_count ?? data.inserted ?? 0;
      toast.success(`Import ${kind}: ${ok} filas procesadas`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const fixMut = useMutation({
    mutationFn: () => adminApi.fixApellidos(),
    onSuccess: (d) => toast.success(d.message ?? `Apellidos corregidos${d.fixed ? ` (${d.fixed})` : ""}`),
    onError: (e: Error) => toast.error(e.message),
  });

  const resetMut = useMutation({
    mutationFn: () => adminApi.resetClientesDesdeBackup(),
    onSuccess: (d) => {
      toast.success(d.message ?? "Clientes restaurados desde backup");
      setConfirmReset(false);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-4xl mx-auto">
      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Back-office
        </div>
        <h1 className="font-display text-3xl text-ink">Settings</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Importación de datos legacy y herramientas de mantenimiento.
        </p>
      </header>

      <CambioYPreciosSection />

      <CategoriasSection />
      <SpecTemplatesSection />
      <MarcasSection />
      <EtiquetasSection />
      <ClasificacionSection />

      <section className="rounded-lg border hairline bg-background p-4 space-y-3">
        <h2 className="font-display text-lg text-ink">Imports CSV</h2>
        <p className="text-sm text-muted-foreground">
          Subí archivos CSV exportados desde el sistema viejo o planillas. UTF-8, con headers en la primera fila.
        </p>

        <div className="grid md:grid-cols-3 gap-3">
          <ImportCard
            kind="equipos"
            label="Equipos"
            hint="Headers: nombre, marca, modelo, cantidad, precio_jornada…"
            onPick={(f) => importMut.mutate({ kind: "equipos", file: f })}
            busy={importMut.isPending && importMut.variables?.kind === "equipos"}
            result={results.equipos}
          />
          <ImportCard
            kind="clientes"
            label="Clientes"
            hint="Headers: nombre, apellido, email, telefono, cuit…"
            onPick={(f) => importMut.mutate({ kind: "clientes", file: f })}
            busy={importMut.isPending && importMut.variables?.kind === "clientes"}
            result={results.clientes}
          />
          <ImportCard
            kind="alquileres"
            label="Alquileres"
            hint="Headers: numero_pedido, cliente, fecha_desde, fecha_hasta, items…"
            onPick={(f) => importMut.mutate({ kind: "alquileres", file: f })}
            busy={importMut.isPending && importMut.variables?.kind === "alquileres"}
            result={results.alquileres}
          />
        </div>
      </section>

      <section className="rounded-lg border hairline bg-background p-4 space-y-3">
        <h2 className="font-display text-lg text-ink">Mantenimiento</h2>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-t hairline pt-3">
          <div>
            <div className="text-ink">Corregir apellidos</div>
            <p className="text-xs text-muted-foreground">
              Recorre clientes y separa apellido del nombre cuando vinieron juntos.
            </p>
          </div>
          <Button variant="outline" onClick={() => fixMut.mutate()} disabled={fixMut.isPending}>
            <Wrench className="h-4 w-4 mr-1" />
            {fixMut.isPending ? "Procesando…" : "Ejecutar"}
          </Button>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-t hairline pt-3">
          <div>
            <div className="text-ink flex items-center gap-1.5">
              <AlertTriangle className="h-4 w-4 text-destructive" />
              Restaurar clientes desde backup
            </div>
            <p className="text-xs text-muted-foreground">
              Reemplaza la tabla de clientes por la versión del backup. Destructivo.
            </p>
          </div>
          <Button
            variant="outline"
            className="border-destructive/40 text-destructive hover:bg-destructive/5"
            onClick={() => setConfirmReset(true)}
          >
            Restaurar
          </Button>
        </div>
      </section>

      <AlertDialog open={confirmReset} onOpenChange={setConfirmReset}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Restaurar clientes desde backup?</AlertDialogTitle>
            <AlertDialogDescription>
              Esta acción reemplaza la tabla de clientes actual con la versión guardada en el backup.
              Cualquier cliente nuevo creado después se perderá.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => resetMut.mutate()}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Sí, restaurar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function ImportCard({
  label, hint, onPick, busy, result,
}: {
  kind: Kind;
  label: string;
  hint: string;
  onPick: (file: File) => void;
  busy: boolean;
  result: ImportCsvResp | null;
}) {
  const ref = useRef<HTMLInputElement>(null);
  return (
    <div className="rounded-md border hairline p-3 space-y-2">
      <div className="font-display text-base text-ink">{label}</div>
      <p className="text-xs text-muted-foreground min-h-8">{hint}</p>
      <input
        ref={ref}
        type="file"
        accept=".csv"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onPick(f);
          e.target.value = "";
        }}
      />
      <Button
        variant="outline"
        size="sm"
        className="w-full"
        onClick={() => ref.current?.click()}
        disabled={busy}
      >
        <Upload className="h-4 w-4 mr-1" />
        {busy ? "Subiendo…" : "Elegir CSV"}
      </Button>

      {result && (
        <div className="text-xs space-y-1 pt-1 border-t hairline">
          <div className="font-mono text-muted-foreground">
            ✓ {result.success_count ?? result.inserted ?? 0} ok
            {result.skipped ? ` · ${result.skipped} skip` : ""}
            {(result.errors?.length ?? result.error_details?.length) ?
              ` · ${result.errors?.length ?? result.error_details?.length} err` : ""}
          </div>
          {(result.errors ?? result.error_details ?? []).slice(0, 3).map((err, i) => (
            <div key={i} className="text-destructive truncate">{err}</div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Categorías: prioridad / orden
// ─────────────────────────────────────────────────────────────────────────

function CategoriasSection() {
  const qc = useQueryClient();
  const listQ = useQuery({
    queryKey: ["admin", "categorias"],
    queryFn: () => adminApi.adminListCategorias(),
  });

  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  const [newChildFor, setNewChildFor] = useState<number | null>(null);
  const [newChildName, setNewChildName] = useState("");
  const [newRoot, setNewRoot] = useState("");

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin", "categorias"] });
    qc.invalidateQueries({ queryKey: ["categorias"] });
    qc.invalidateQueries({ queryKey: ["equipos"] });
  };

  const updateMut = useMutation({
    mutationFn: ({ id, ...patch }: { id: number; nombre?: string; prioridad?: number; parent_id?: number | null; set_parent_null?: boolean }) =>
      adminApi.adminUpdateCategoria(id, patch),
    onSuccess: invalidate,
    onError: (e: Error) => toast.error(e.message),
  });

  const createMut = useMutation({
    mutationFn: (data: { nombre: string; prioridad?: number; parent_id?: number | null }) =>
      adminApi.adminCreateCategoria(data),
    onSuccess: () => { invalidate(); toast.success("Categoría creada"); },
    onError: (e: Error) => toast.error(e.message),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => adminApi.adminDeleteCategoria(id),
    onSuccess: () => { invalidate(); toast.success("Categoría eliminada"); },
    onError: (e: Error) => toast.error(e.message),
  });

  // Construir árbol desde la lista plana.
  const tree = useMemo(() => {
    const all = listQ.data ?? [];
    const roots = all
      .filter((e) => e.parent_id == null)
      .sort((a, b) => a.prioridad - b.prioridad || a.nombre.localeCompare(b.nombre));
    const childrenOf = (pid: number) =>
      all
        .filter((e) => e.parent_id === pid)
        .sort((a, b) => a.prioridad - b.prioridad || a.nombre.localeCompare(b.nombre));
    return { roots, childrenOf, all };
  }, [listQ.data]);

  return (
    <section className="rounded-lg border hairline bg-background p-4 space-y-3">
      <div>
        <h2 className="font-display text-lg text-ink">Categorías</h2>
        <p className="text-sm text-muted-foreground">
          Árbol de 2 niveles. Las subcategorías heredan al padre: filtrar por
          "Cámaras" muestra equipos de Foto, Video y Acción. Menor prioridad = más arriba.
        </p>
      </div>

      {listQ.isLoading && (
        <div className="py-6 text-sm text-muted-foreground flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin" /> Cargando…
        </div>
      )}
      {listQ.error && (
        <div className="text-sm text-destructive">Error: {(listQ.error as Error).message}</div>
      )}

      {tree.roots.length > 0 && (
        <ul className="divide-y hairline border hairline rounded-md">
          {tree.roots.map((root) => {
            const children = tree.childrenOf(root.id);
            const isOpen = expanded[root.id] ?? true;
            return (
              <li key={root.id} className="py-1">
                <CategoryRow
                  et={root}
                  isRoot
                  isOpen={isOpen}
                  hasChildren={children.length > 0}
                  onToggle={() => setExpanded((s) => ({ ...s, [root.id]: !isOpen }))}
                  onPriority={(v) => updateMut.mutate({ id: root.id, prioridad: v })}
                  onRename={(n) => updateMut.mutate({ id: root.id, nombre: n })}
                  onDelete={() => {
                    if (confirm(`Eliminar "${root.nombre}" y desvincular sus hijos?`)) {
                      deleteMut.mutate(root.id);
                    }
                  }}
                  onAddChild={() => { setNewChildFor(root.id); setNewChildName(""); }}
                />
                {isOpen && (
                  <ul className="pl-6">
                    {children.map((child) => (
                      <li key={child.id}>
                        <CategoryRow
                          et={child}
                          parents={tree.roots.filter((r) => r.id !== child.id)}
                          onPriority={(v) => updateMut.mutate({ id: child.id, prioridad: v })}
                          onRename={(n) => updateMut.mutate({ id: child.id, nombre: n })}
                          onChangeParent={(pid) =>
                            updateMut.mutate(
                              pid === null
                                ? { id: child.id, set_parent_null: true }
                                : { id: child.id, parent_id: pid },
                            )
                          }
                          onDelete={() => {
                            if (confirm(`Eliminar subcategoría "${child.nombre}"?`)) {
                              deleteMut.mutate(child.id);
                            }
                          }}
                        />
                      </li>
                    ))}
                    {newChildFor === root.id && (
                      <li className="px-3 py-2 flex items-center gap-2">
                        <Input
                          autoFocus
                          placeholder="Nombre de la subcategoría"
                          value={newChildName}
                          onChange={(e) => setNewChildName(e.target.value)}
                          className="h-8 flex-1"
                          onKeyDown={(e) => {
                            if (e.key === "Enter" && newChildName.trim()) {
                              createMut.mutate({ nombre: newChildName.trim(), parent_id: root.id });
                              setNewChildFor(null);
                            }
                            if (e.key === "Escape") setNewChildFor(null);
                          }}
                        />
                        <Button
                          size="sm"
                          disabled={!newChildName.trim() || createMut.isPending}
                          onClick={() => {
                            createMut.mutate({ nombre: newChildName.trim(), parent_id: root.id });
                            setNewChildFor(null);
                          }}
                        >
                          Agregar
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => setNewChildFor(null)}>
                          Cancelar
                        </Button>
                      </li>
                    )}
                  </ul>
                )}
              </li>
            );
          })}
        </ul>
      )}

      <div className="flex items-center gap-2 pt-2">
        <Input
          placeholder="Nueva categoría raíz"
          value={newRoot}
          onChange={(e) => setNewRoot(e.target.value)}
          className="h-8 max-w-xs"
          onKeyDown={(e) => {
            if (e.key === "Enter" && newRoot.trim()) {
              createMut.mutate({ nombre: newRoot.trim(), parent_id: null });
              setNewRoot("");
            }
          }}
        />
        <Button
          size="sm"
          disabled={!newRoot.trim() || createMut.isPending}
          onClick={() => {
            createMut.mutate({ nombre: newRoot.trim(), parent_id: null });
            setNewRoot("");
          }}
        >
          <Plus className="h-4 w-4 mr-1" /> Agregar raíz
        </Button>
      </div>
    </section>
  );
}

type RowItem = { id: number; nombre: string; prioridad: number; parent_id: number | null; total: number };

function CategoryRow({
  et, isRoot, isOpen, hasChildren, parents, onToggle, onPriority,
  onRename, onChangeParent, onDelete, onAddChild,
}: {
  et: RowItem;
  isRoot?: boolean;
  isOpen?: boolean;
  hasChildren?: boolean;
  parents?: RowItem[];
  onToggle?: () => void;
  onPriority: (v: number) => void;
  onRename: (n: string) => void;
  onChangeParent?: (parentId: number | null) => void;
  onDelete: () => void;
  onAddChild?: () => void;
}) {
  return (
    <div className="flex items-center gap-2 px-3 py-1.5">
      {isRoot ? (
        <button
          type="button"
          onClick={onToggle}
          className="h-6 w-6 grid place-items-center text-muted-foreground"
          aria-label={isOpen ? "Colapsar" : "Expandir"}
        >
          {hasChildren ? (
            isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />
          ) : <span className="h-4 w-4 inline-block" />}
        </button>
      ) : (
        <span className="h-6 w-6 inline-block" />
      )}
      <Input
        defaultValue={et.nombre}
        key={`${et.id}-name-${et.nombre}`}
        className={`h-8 flex-1 ${isRoot ? "font-medium" : ""}`}
        onBlur={(e) => {
          const v = e.target.value.trim();
          if (v && v !== et.nombre) onRename(v);
        }}
      />
      <span className="text-[11px] text-muted-foreground tabular-nums w-10 text-right">
        {et.total}
      </span>
      {!isRoot && parents && onChangeParent && (
        <Select
          value={et.parent_id ? String(et.parent_id) : "none"}
          onValueChange={(v) => onChangeParent(v === "none" ? null : Number(v))}
        >
          <SelectTrigger className="h-8 w-32 text-xs"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="none">Sin padre</SelectItem>
            {parents.map((p) => (
              <SelectItem key={p.id} value={String(p.id)}>{p.nombre}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}
      <Input
        type="number"
        defaultValue={et.prioridad}
        key={`${et.id}-pri-${et.prioridad}`}
        className="h-8 w-16 text-right tabular-nums"
        onBlur={(e) => {
          const v = parseInt(e.target.value);
          if (!Number.isNaN(v) && v !== et.prioridad) onPriority(v);
        }}
      />
      {isRoot && onAddChild && (
        <Button size="icon" variant="ghost" className="h-8 w-8" onClick={onAddChild} title="Agregar subcategoría">
          <Plus className="h-4 w-4" />
        </Button>
      )}
      <Button size="icon" variant="ghost" className="h-8 w-8 text-destructive" onClick={onDelete} title="Eliminar">
        <Trash2 className="h-4 w-4" />
      </Button>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Etiquetas (bolsa libre, plana — keywords manuales)
// ─────────────────────────────────────────────────────────────────────────

function EtiquetasSection() {
  const qc = useQueryClient();
  const listQ = useQuery({
    queryKey: ["admin", "etiquetas"],
    queryFn: () => adminApi.adminListEtiquetas(),
  });
  const [nueva, setNueva] = useState("");
  const [filter, setFilter] = useState("");

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin", "etiquetas"] });
    qc.invalidateQueries({ queryKey: ["etiquetas"] });
  };

  const createMut = useMutation({
    mutationFn: (nombre: string) => adminApi.adminCreateEtiqueta({ nombre }),
    onSuccess: () => { invalidate(); setNueva(""); toast.success("Etiqueta creada"); },
    onError: (e: Error) => toast.error(e.message),
  });
  const renameMut = useMutation({
    mutationFn: ({ id, nombre }: { id: number; nombre: string }) =>
      adminApi.adminUpdateEtiqueta(id, { nombre }),
    onSuccess: invalidate,
    onError: (e: Error) => toast.error(e.message),
  });
  const deleteMut = useMutation({
    mutationFn: (id: number) => adminApi.adminDeleteEtiqueta(id),
    onSuccess: () => { invalidate(); toast.success("Etiqueta eliminada"); },
    onError: (e: Error) => toast.error(e.message),
  });

  // Mostramos solo etiquetas manuales (las que tienen al menos 1 uso o las que
  // el admin creó a mano y todavía no asignó). Como el endpoint admin devuelve
  // TODO (incluyendo auto-tags derivadas), filtramos visualmente: las auto
  // típicamente son lowercase y sin prioridad customizada (= 100). El criterio
  // exacto es difuso; mostramos todas y dejamos que el admin filtre por texto.
  const items = useMemo(() => {
    const all = listQ.data ?? [];
    const f = filter.trim().toLowerCase();
    const list = f ? all.filter((e) => e.nombre.toLowerCase().includes(f)) : all;
    return list.sort((a, b) => b.total - a.total || a.nombre.localeCompare(b.nombre));
  }, [listQ.data, filter]);

  return (
    <section className="rounded-lg border hairline bg-background p-4 space-y-3">
      <div>
        <h2 className="font-display text-lg text-ink">Etiquetas libres</h2>
        <p className="text-sm text-muted-foreground">
          Bolsa de keywords para búsqueda. Marca, modelo, nombre y categorías
          se agregan automáticamente — usá esto para palabras adicionales (ej:
          "f/2.8", "4k60", "fullframe", "bicolor").
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Input
          placeholder="Nueva etiqueta…"
          value={nueva}
          onChange={(e) => setNueva(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && nueva.trim()) createMut.mutate(nueva.trim());
          }}
          className="h-8 max-w-xs"
        />
        <Button size="sm" disabled={!nueva.trim() || createMut.isPending}
          onClick={() => createMut.mutate(nueva.trim())}>
          <Plus className="h-4 w-4 mr-1" /> Agregar
        </Button>
        <div className="flex-1" />
        <Input
          placeholder="Filtrar…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="h-8 max-w-xs"
        />
      </div>

      {listQ.isLoading && (
        <div className="py-6 text-sm text-muted-foreground flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin" /> Cargando…
        </div>
      )}
      {listQ.error && (
        <div className="text-sm text-destructive">Error: {(listQ.error as Error).message}</div>
      )}

      {items.length > 0 && (
        <ul className="divide-y hairline border hairline rounded-md max-h-96 overflow-auto">
          {items.map((et) => (
            <li key={et.id} className="flex items-center gap-2 px-3 py-1.5">
              <Input
                defaultValue={et.nombre}
                key={`${et.id}-${et.nombre}`}
                className="h-8 flex-1"
                onBlur={(e) => {
                  const v = e.target.value.trim();
                  if (v && v !== et.nombre) renameMut.mutate({ id: et.id, nombre: v });
                }}
              />
              <span className="text-[11px] text-muted-foreground tabular-nums w-10 text-right">
                {et.total}
              </span>
              <Button size="icon" variant="ghost" className="h-8 w-8 text-destructive"
                onClick={() => {
                  if (confirm(`Eliminar etiqueta "${et.nombre}"?`)) deleteMut.mutate(et.id);
                }} title="Eliminar">
                <Trash2 className="h-4 w-4" />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function ClasificacionSection() {
  const qc = useQueryClient();
  const [preview, setPreview] = useState<ClasificarResult | null>(null);

  const dryRunMut = useMutation({
    mutationFn: () => adminApi.adminClasificarDryRun(),
    onSuccess: (r) => setPreview(r),
    onError: (e: Error) => toast.error(e.message),
  });

  const applyMut = useMutation({
    mutationFn: () => adminApi.adminClasificarApply(),
    onSuccess: (r) => {
      toast.success(`${r.applied} equipos clasificados`);
      setPreview(r);
      qc.invalidateQueries({ queryKey: ["categorias"] });
      qc.invalidateQueries({ queryKey: ["equipos"] });
      qc.invalidateQueries({ queryKey: ["admin", "etiquetas"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <section className="rounded-lg border hairline bg-background p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="font-display text-lg text-ink flex items-center gap-2">
            <Sparkles className="h-4 w-4" /> Clasificación automática de equipos
          </h2>
          <p className="text-sm text-muted-foreground">
            Aplica reglas por nombre/marca/modelo para asignar etiquetas hoja a cada equipo.
            Equipos como la a7 V se asignan a Foto y Video. Revisá el preview antes de aplicar
            — al aplicar, las etiquetas existentes de cada equipo con match se reemplazan.
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="outline" disabled={dryRunMut.isPending} onClick={() => dryRunMut.mutate()}>
          {dryRunMut.isPending && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}
          Generar preview
        </Button>
        {preview && (
          <Button
            size="sm"
            disabled={applyMut.isPending || preview.matched === 0}
            onClick={() => {
              if (confirm(`Aplicar clasificación a ${preview.matched} equipos? Las etiquetas existentes serán reemplazadas.`)) {
                applyMut.mutate();
              }
            }}
          >
            {applyMut.isPending && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}
            Aplicar a {preview.matched} equipos
          </Button>
        )}
      </div>

      {preview && (
        <div className="space-y-2">
          <div className="text-xs text-muted-foreground">
            Total: {preview.total} · con match: <strong className="text-ink">{preview.matched}</strong> ·
            sin match: <strong className="text-ink">{preview.unmatched}</strong>
            {preview.applied > 0 && <> · aplicados: <strong className="text-ink">{preview.applied}</strong></>}
          </div>
          <div className="max-h-80 overflow-auto border hairline rounded-md text-xs">
            <table className="w-full">
              <thead className="bg-muted/50 sticky top-0">
                <tr className="text-left">
                  <th className="px-2 py-1.5 font-medium">Equipo</th>
                  <th className="px-2 py-1.5 font-medium">Actuales</th>
                  <th className="px-2 py-1.5 font-medium">Propuestas</th>
                </tr>
              </thead>
              <tbody>
                {preview.items.map((it) => (
                  <tr key={it.id} className="border-t hairline">
                    <td className="px-2 py-1.5">
                      <div className="text-ink">{it.nombre}</div>
                      {it.marca && <div className="text-muted-foreground text-[10px]">{it.marca}</div>}
                    </td>
                    <td className="px-2 py-1.5 text-muted-foreground">
                      {it.actuales.length === 0 ? "—" : it.actuales.join(", ")}
                    </td>
                    <td className="px-2 py-1.5">
                      {it.propuestas.length === 0 ? (
                        <span className="text-destructive/80">sin match</span>
                      ) : (
                        <span className="text-ink">{it.propuestas.join(" + ")}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}


// ── Cambio (USD/ARS) y recálculo masivo de precios ─────────────────────────

type RecalcMode = "missing" | "auto" | "all" | "ids";

function CambioYPreciosSection() {
  const qc = useQueryClient();
  const [valor, setValor] = useState("");
  const [confirmRecalc, setConfirmRecalc] = useState<{
    mode: RecalcMode;
    ids?: number[];
    preview: { total_cambios: number; total_evaluados: number };
  } | null>(null);

  const settingQ = useQuery({
    queryKey: ["settings", "usd_rate"],
    queryFn: () => adminApi.getSetting("usd_rate"),
    staleTime: 60_000,
  });

  // Cargar el valor actual cuando llega de la red.
  useEffect(() => {
    if (settingQ.data && !valor) setValor(settingQ.data.value);
  }, [settingQ.data, valor]);

  const updateMut = useMutation({
    mutationFn: (v: string) => adminApi.updateSetting("usd_rate", v),
    onSuccess: () => {
      toast.success("Tipo de cambio actualizado");
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const dryRunMut = useMutation({
    mutationFn: (args: { mode: RecalcMode; ids?: number[] }) =>
      adminApi.recalcularPrecios({ dry_run: true, ...args }).then((r) => ({ ...r, ...args })),
    onSuccess: (r) => {
      if (r.total_cambios === 0) {
        toast.info("Nada para recalcular — todos los precios ya están en sincro.");
        return;
      }
      setConfirmRecalc({
        mode: r.mode,
        ids: r.ids,
        preview: { total_cambios: r.total_cambios, total_evaluados: r.total_evaluados },
      });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const applyMut = useMutation({
    mutationFn: (args: { mode: RecalcMode; ids?: number[] }) =>
      adminApi.recalcularPrecios({ dry_run: false, ...args }),
    onSuccess: (r) => {
      toast.success(`${r.total_cambios} precios actualizados`);
      qc.invalidateQueries({ queryKey: ["admin", "equipos"] });
      qc.invalidateQueries({ queryKey: ["equipos"] });
      qc.invalidateQueries({ queryKey: ["admin", "precios-manuales"] });
      setConfirmRecalc(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const dirty = valor.trim() !== (settingQ.data?.value ?? "");
  const fmtFecha = (s: string | null) => {
    if (!s) return "—";
    try {
      return new Date(s).toLocaleString("es-AR", {
        dateStyle: "medium", timeStyle: "short",
      });
    } catch {
      return s;
    }
  };
  const modeLabel = (m: RecalcMode) => ({
    missing: "Sólo equipos sin precio",
    auto: "Sólo precios automáticos",
    all: "Todos (incluye manuales)",
    ids: "Selección personalizada",
  }[m]);

  return (
    <>
      <section className="rounded-lg border hairline bg-background p-4 space-y-3">
        <header>
          <h2 className="font-display text-lg text-ink">Tipo de cambio &amp; precios</h2>
          <p className="text-sm text-muted-foreground">
            Cotización del dólar usada para calcular el precio de jornada en pesos.
            Actualizalo a fin de mes y después aplicá el recálculo masivo.
          </p>
        </header>

        <div className="flex flex-col sm:flex-row sm:items-end gap-3 border-t hairline pt-3">
          <div className="flex-1">
            <label className="text-xs uppercase tracking-wide text-muted-foreground">
              ARS por 1 USD
            </label>
            <Input
              type="number"
              min={0}
              step="0.01"
              value={valor}
              onChange={(e) => setValor(e.target.value)}
              placeholder="1200"
              className="mt-1"
            />
            <p className="mt-1 text-[11px] text-muted-foreground">
              Última actualización: {fmtFecha(settingQ.data?.updated_at ?? null)}
              {settingQ.data?.updated_by && ` · ${settingQ.data.updated_by}`}
            </p>
          </div>
          <Button
            onClick={() => updateMut.mutate(valor)}
            disabled={!dirty || updateMut.isPending || !valor.trim()}
          >
            {updateMut.isPending ? "Guardando…" : "Guardar"}
          </Button>
        </div>

        <div className="border-t hairline pt-3 space-y-2">
          <div>
            <div className="text-ink font-medium">Recalcular precios</div>
            <p className="text-xs text-muted-foreground">
              <code className="font-mono text-[11px] bg-muted/50 px-1 py-0.5 rounded">
                precio_jornada = precio_usd × usd_rate × (roi_pct / 100)
              </code>
              {" "}— redondeado al múltiplo de 100 más cercano.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline" size="sm"
              onClick={() => dryRunMut.mutate({ mode: "auto" })}
              disabled={dryRunMut.isPending}
              title="Respeta los precios marcados como manuales"
            >
              {dryRunMut.isPending ? (
                <><Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />Calculando…</>
              ) : (
                "Sólo automáticos (recomendado)"
              )}
            </Button>
            <Button
              variant="ghost" size="sm"
              onClick={() => dryRunMut.mutate({ mode: "missing" })}
              disabled={dryRunMut.isPending}
              title="Sólo equipos que aún no tienen precio cargado"
            >
              Sólo sin precio
            </Button>
            <Button
              variant="ghost" size="sm"
              onClick={() => dryRunMut.mutate({ mode: "all" })}
              disabled={dryRunMut.isPending}
              title="Pisa los precios manuales también — usar con cuidado"
              className="text-destructive hover:text-destructive"
            >
              Todos (pisa manuales)
            </Button>
          </div>
        </div>

        <PreciosManualesPanel
          onRecalcSelected={(ids) => dryRunMut.mutate({ mode: "ids", ids })}
        />
      </section>

      <AlertDialog open={!!confirmRecalc} onOpenChange={(v) => { if (!v) setConfirmRecalc(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              ¿Aplicar recálculo a {confirmRecalc?.preview.total_cambios} equipos?
            </AlertDialogTitle>
            <AlertDialogDescription>
              Modo: <strong>{confirmRecalc && modeLabel(confirmRecalc.mode)}</strong>.
              {" "}De {confirmRecalc?.preview.total_evaluados} equipos evaluados,
              {" "}{confirmRecalc?.preview.total_cambios} cambiarían su precio en pesos.
              {confirmRecalc?.mode === "all" && (
                <span className="block mt-2 text-destructive">
                  ⚠️ Vas a pisar también los precios marcados como manuales.
                </span>
              )}
              {" "}Esta acción no se puede deshacer automáticamente.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                confirmRecalc && applyMut.mutate({
                  mode: confirmRecalc.mode,
                  ids: confirmRecalc.ids,
                })
              }
              disabled={applyMut.isPending}
            >
              {applyMut.isPending ? "Aplicando…" : "Sí, aplicar"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}


/** Lista los equipos con precio_jornada_manual=TRUE y muestra qué precio
 *  daría la fórmula con el USD rate actual. Permite seleccionar manualmente
 *  cuáles recalcular (los demás conservan su precio fijado). */
function PreciosManualesPanel({
  onRecalcSelected,
}: {
  onRecalcSelected: (ids: number[]) => void;
}) {
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [expanded, setExpanded] = useState(false);

  const manualesQ = useQuery({
    queryKey: ["admin", "precios-manuales"],
    queryFn: () => adminApi.listarPreciosManuales(),
    staleTime: 30_000,
  });

  const items = manualesQ.data?.items ?? [];
  const conDelta = items.filter((i) => i.delta != null && i.delta !== 0);

  if (manualesQ.isLoading) {
    return (
      <div className="border-t hairline pt-3 text-xs text-muted-foreground">
        Cargando precios manuales…
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="border-t hairline pt-3 text-xs text-muted-foreground">
        No hay equipos con precio fijado manualmente.
      </div>
    );
  }

  const toggleAll = () => {
    if (selected.size === conDelta.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(conDelta.map((i) => i.id)));
    }
  };

  const toggleOne = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const fmtPrecio = (n: number | null) =>
    n == null ? "—" : `$${Math.round(n).toLocaleString("es-AR", { maximumFractionDigits: 0 })}`;

  return (
    <div className="border-t hairline pt-3 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <div>
          <div className="text-ink font-medium text-sm">
            Precios manuales — revisión equipo por equipo
          </div>
          <p className="text-xs text-muted-foreground">
            {items.length} equipos con precio fijado a mano.{" "}
            {conDelta.length > 0
              ? `${conDelta.length} cambiarían con el USD actual.`
              : "Todos coinciden con la fórmula actual."}
          </p>
        </div>
        <Button
          variant="ghost" size="sm"
          onClick={() => setExpanded((e) => !e)}
          className="shrink-0 h-7 text-xs"
        >
          {expanded ? "Ocultar" : "Revisar"}
        </Button>
      </div>

      {expanded && (
        <div className="rounded-md border hairline bg-muted/20 max-h-96 overflow-y-auto">
          {conDelta.length > 0 && (
            <div className="sticky top-0 z-10 flex items-center justify-between gap-2 px-3 py-2 border-b hairline bg-background/95 backdrop-blur">
              <button
                type="button"
                onClick={toggleAll}
                className="text-[11px] underline hover:text-ink"
              >
                {selected.size === conDelta.length ? "Deseleccionar todos" : "Seleccionar todos los que cambian"}
              </button>
              <Button
                size="sm" className="h-7 text-xs"
                disabled={selected.size === 0}
                onClick={() => onRecalcSelected([...selected])}
              >
                Recalcular {selected.size > 0 ? `(${selected.size})` : ""}
              </Button>
            </div>
          )}
          <table className="w-full text-xs">
            <thead className="text-[10px] uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="text-left px-3 py-1.5 w-8"></th>
                <th className="text-left px-3 py-1.5">Equipo</th>
                <th className="text-right px-3 py-1.5">Actual</th>
                <th className="text-right px-3 py-1.5">Si recalcula</th>
                <th className="text-right px-3 py-1.5">Δ</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => {
                const cambia = it.delta != null && it.delta !== 0;
                return (
                  <tr key={it.id} className="border-t hairline">
                    <td className="px-3 py-1.5">
                      <input
                        type="checkbox"
                        checked={selected.has(it.id)}
                        disabled={!cambia}
                        onChange={() => toggleOne(it.id)}
                        className="cursor-pointer"
                      />
                    </td>
                    <td className="px-3 py-1.5 text-ink">
                      {it.nombre}
                      {(it.marca || it.modelo) && (
                        <span className="text-muted-foreground">
                          {" "}— {[it.marca, it.modelo].filter(Boolean).join(" / ")}
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums">
                      {fmtPrecio(it.precio_actual)}
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-muted-foreground">
                      {fmtPrecio(it.precio_calculado)}
                    </td>
                    <td className={
                      "px-3 py-1.5 text-right tabular-nums " +
                      (cambia ? (it.delta! > 0 ? "text-emerald-600" : "text-destructive") : "text-muted-foreground")
                    }>
                      {cambia
                        ? `${it.delta! > 0 ? "+" : ""}${fmtPrecio(it.delta).slice(1)}`
                        : "—"}
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

// ─────────────────────────────────────────────────────────────────────────
// Marcas: visibilidad y orden (drag-drop)
// ─────────────────────────────────────────────────────────────────────────

function MarcasSection() {
  const qc = useQueryClient();
  const listQ = useQuery({
    queryKey: ["admin", "marcas"],
    queryFn: () => adminApi.adminListMarcas(),
  });

  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<MarcaAdmin[]>([]);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin", "marcas"] });
    qc.invalidateQueries({ queryKey: ["marcas"] });
    qc.invalidateQueries({ queryKey: ["equipos"] });
  };

  const updateMut = useMutation({
    mutationFn: ({ id, ...patch }: { id: number } & Partial<MarcaAdmin>) =>
      adminApi.adminUpdateMarca(id, patch),
    onSuccess: invalidate,
    onError: (e: Error) => toast.error(e.message),
  });

  const reorderMut = useMutation({
    mutationFn: (reorder: { id: number; orden: number }[]) =>
      adminApi.adminReorderMarcas(reorder),
    onSuccess: invalidate,
    onError: (e: Error) => toast.error(e.message),
  });

  const allMarcas = listQ.data?.items ?? [];

  // Cargar marcas visibles al iniciar
  useEffect(() => {
    if (allMarcas.length > 0 && selected.length === 0) {
      setSelected(allMarcas.filter((m) => m.visible).sort((a, b) => a.orden - b.orden));
    }
  }, [allMarcas, selected.length]);

  const filteredAvailable = useMemo(() => {
    const f = search.trim().toLowerCase();
    const selectedIds = new Set(selected.map((m) => m.id));
    return allMarcas
      .filter((m) => !selectedIds.has(m.id) && m.nombre.toLowerCase().includes(f))
      .sort((a, b) => a.nombre.localeCompare(b.nombre));
  }, [allMarcas, selected, search]);

  const handleSelectMarca = (marca: MarcaAdmin) => {
    const nextOrden = Math.max(...selected.map((m) => m.orden), 99) + 1;
    setSelected([...selected, { ...marca, orden: nextOrden, visible: true }]);
  };

  const handleRemoveMarca = (id: number) => {
    const marca = selected.find((m) => m.id === id);
    if (marca) {
      updateMut.mutate({ id, visible: false });
    }
    setSelected(selected.filter((m) => m.id !== id));
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const oldIndex = selected.findIndex((m) => m.id === active.id);
    const newIndex = selected.findIndex((m) => m.id === over.id);

    const newOrder = arrayMove(selected, oldIndex, newIndex);
    setSelected(newOrder);

    // Update orden en el backend
    const updates = newOrder.map((m, i) => ({ id: m.id, orden: i * 10 }));
    reorderMut.mutate(updates);
  };

  const toggleVisible = (id: number, currentVis: boolean) => {
    updateMut.mutate({ id, visible: !currentVis });
  };

  const sensors = useSensors(
    useSensor(PointerSensor, { distance: 8 }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  return (
    <section className="rounded-lg border hairline bg-background p-4 space-y-3">
      <div>
        <h2 className="font-display text-lg text-ink">Marcas</h2>
        <p className="text-sm text-muted-foreground">
          Selecciona qué marcas quieres que aparezcan en el carrusel público y ordénalas con drag-drop.
        </p>
      </div>

      {listQ.isLoading && (
        <div className="py-6 text-sm text-muted-foreground flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin" /> Cargando…
        </div>
      )}
      {listQ.error && (
        <div className="text-sm text-destructive">Error: {(listQ.error as Error).message}</div>
      )}

      {!listQ.isLoading && (
        <div className="grid grid-cols-2 gap-4">
          {/* Disponibles */}
          <div className="space-y-2">
            <div>
              <label className="text-xs uppercase tracking-wide text-muted-foreground">
                Disponibles
              </label>
              <Input
                placeholder="Buscar marca…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="h-8 mt-1"
              />
            </div>
            <div className="border hairline rounded-md p-2 space-y-1 max-h-96 overflow-auto">
              {filteredAvailable.length > 0 ? (
                filteredAvailable.map((marca) => (
                  <button
                    key={marca.id}
                    onClick={() => handleSelectMarca(marca)}
                    className="w-full text-left flex items-center gap-2 rounded px-2 py-1.5 hover:bg-muted transition text-sm"
                  >
                    {marca.logo_url && (
                      <img
                        src={marca.logo_url}
                        alt={marca.nombre}
                        className="h-5 w-5 object-contain"
                        onError={(e) => (e.currentTarget.style.display = "none")}
                      />
                    )}
                    <span className="flex-1">{marca.nombre}</span>
                    <span className="text-xs text-muted-foreground">({marca.total})</span>
                  </button>
                ))
              ) : (
                <div className="text-xs text-muted-foreground py-2 text-center">
                  {search ? "Sin resultados" : "Todas seleccionadas"}
                </div>
              )}
            </div>
          </div>

          {/* Seleccionadas (con drag-drop) */}
          <div className="space-y-2">
            <label className="text-xs uppercase tracking-wide text-muted-foreground">
              Seleccionadas ({selected.length})
            </label>
            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
              <SortableContext
                items={selected.map((m) => m.id)}
                strategy={verticalListSortingStrategy}
              >
                <div className="border hairline rounded-md p-2 space-y-1 max-h-96 overflow-auto">
                  {selected.length > 0 ? (
                    selected.map((marca) => (
                      <SortableMarcaItem
                        key={marca.id}
                        marca={marca}
                        onRemove={() => handleRemoveMarca(marca.id)}
                        onToggleVisible={() => toggleVisible(marca.id, marca.visible)}
                        disabled={updateMut.isPending || reorderMut.isPending}
                      />
                    ))
                  ) : (
                    <div className="text-xs text-muted-foreground py-2 text-center">
                      Sin marcas seleccionadas
                    </div>
                  )}
                </div>
              </SortableContext>
            </DndContext>
          </div>
        </div>
      )}
    </section>
  );
}

function SortableMarcaItem({
  marca,
  onRemove,
  onToggleVisible,
  disabled,
}: {
  marca: MarcaAdmin;
  onRemove: () => void;
  onToggleVisible: () => void;
  disabled: boolean;
}) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({
    id: marca.id,
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="flex items-center gap-2 rounded px-2 py-1.5 bg-muted/50 text-sm group"
    >
      <button
        {...attributes}
        {...listeners}
        className="cursor-grab active:cursor-grabbing h-4 w-4 text-muted-foreground hover:text-foreground flex-shrink-0"
        title="Arrastrar para reordenar"
      >
        <GripVertical className="h-4 w-4" />
      </button>

      {marca.logo_url && (
        <img
          src={marca.logo_url}
          alt={marca.nombre}
          className="h-5 w-5 object-contain flex-shrink-0"
          onError={(e) => (e.currentTarget.style.display = "none")}
        />
      )}

      <div className="flex-1 min-w-0">
        <div className="truncate text-ink">{marca.nombre}</div>
        <div className="text-[10px] text-muted-foreground">{marca.total} equipos</div>
      </div>

      <input
        type="checkbox"
        checked={marca.visible}
        onChange={onToggleVisible}
        disabled={disabled}
        className="h-4 w-4 flex-shrink-0 cursor-pointer"
        title={marca.visible ? "Ocultar" : "Mostrar"}
      />

      <button
        onClick={onRemove}
        disabled={disabled}
        className="h-4 w-4 flex-shrink-0 text-muted-foreground hover:text-destructive transition disabled:opacity-50"
        title="Remover"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
