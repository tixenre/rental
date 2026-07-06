/**
 * MarcasSection — gestión unificada de marcas (#292).
 *
 * Una sola columna con todas las marcas. Cada fila tiene:
 *  - Drag handle (solo activo entre destacadas — controla orden del carrusel).
 *  - Logo (o iniciales como fallback).
 *  - Nombre + count de equipos.
 *  - Toggle ⭐ "destacada" (mostrar en carrusel público del home).
 *  - Mini menú ⋯ con: subir logo, renombrar, ver productos, eliminar.
 *
 * Reemplaza el diseño de doble columna (Disponibles / Seleccionadas) que
 * duplicaba acciones (checkbox + estrella + X). Ver issue #292.
 */

import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import {
  GripVertical,
  AlertTriangle,
  ArrowRight,
  Star,
  MoreHorizontal,
  Upload,
  Pencil,
  ExternalLink,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

import { Input } from "@/design-system/ui/input";
import { Button } from "@/design-system/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/design-system/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/design-system/ui/alert-dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from "@/design-system/ui/dropdown-menu";
import { adminApi, type MarcaAdmin } from "@/lib/admin/api";
import { ListSkeleton } from "@/components/admin/skeletons";
import { ErrorState } from "@/components/admin/ErrorState";
import { useConfirm } from "@/components/admin/useConfirm";
import { InlineSvg } from "@/design-system/ui/InlineSvg";
import { isSvgUrl } from "@/design-system/ui/inline-svg-utils";

export function MarcasSection() {
  const qc = useQueryClient();
  const confirm = useConfirm();
  const navigate = useNavigate();
  const listQ = useQuery({
    queryKey: ["admin", "marcas"],
    queryFn: () => adminApi.adminListMarcas(),
  });

  const [search, setSearch] = useState("");
  const [onlyDestacadas, setOnlyDestacadas] = useState(false);
  const [renaming, setRenaming] = useState<MarcaAdmin | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [deleting, setDeleting] = useState<MarcaAdmin | null>(null);
  const uploadingForId = useRef<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
    mutationFn: (reorder: { id: number; orden: number }[]) => adminApi.adminReorderMarcas(reorder),
    onSuccess: invalidate,
    onError: (e: Error) => toast.error(e.message),
  });

  const mergeMut = useMutation({
    mutationFn: ({ sourceId, targetId }: { sourceId: number; targetId: number }) =>
      adminApi.adminMergeMarcas(sourceId, targetId),
    onSuccess: (data) => {
      toast.success(`Marcas fusionadas en "${data.merged_into}"`);
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => adminApi.adminDeleteMarca(id),
    onSuccess: () => {
      toast.success("Marca eliminada");
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const uploadLogoMut = useMutation({
    mutationFn: ({ id, file }: { id: number; file: File }) =>
      adminApi.adminUploadMarcaLogo(id, file),
    onSuccess: () => {
      toast.success("Logo actualizado");
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const allMarcas = useMemo(() => listQ.data?.items ?? [], [listQ.data?.items]);

  // ── Detección de duplicadas (intacta vs versión anterior) ──────────────
  // NO usa el motor de búsqueda (`lib/search/normalize`) a propósito: acá se
  // agrupa por la PRIMERA palabra plegando solo case+acentos, conservando la
  // puntuación interna. La normalización de búsqueda colapsa los no-alfanuméricos
  // a espacio ("B&H" → "b h"), lo que partiría mal la marca y agruparía falsos
  // duplicados. Es otra operación, no una variante ad-hoc de la búsqueda.
  const duplicateGroups = useMemo(() => {
    const norm = (s: string) =>
      s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").trim().split(/\s+/)[0] ?? "";
    const groups = new Map<string, MarcaAdmin[]>();
    for (const m of allMarcas) {
      const k = norm(m.nombre);
      if (!k) continue;
      if (!groups.has(k)) groups.set(k, []);
      groups.get(k)!.push(m);
    }
    return Array.from(groups.values())
      .filter((g) => g.length > 1)
      .sort((a, b) => b.reduce((s, m) => s + m.total, 0) - a.reduce((s, m) => s + m.total, 0));
  }, [allMarcas]);

  // ── Listas: destacadas (drag-drop) y otras (alfabético por count) ─────
  const destacadas = useMemo(() => {
    return [...allMarcas]
      .filter((m) => m.destacada)
      .sort((a, b) => a.orden - b.orden || a.nombre.localeCompare(b.nombre));
  }, [allMarcas]);

  const otras = useMemo(() => {
    return [...allMarcas]
      .filter((m) => !m.destacada)
      .sort((a, b) => b.total - a.total || a.nombre.localeCompare(b.nombre));
  }, [allMarcas]);

  const filtered = (rows: MarcaAdmin[]) => {
    const f = search.trim().toLowerCase();
    if (!f) return rows;
    return rows.filter((m) => m.nombre.toLowerCase().includes(f));
  };

  const destacadasShown = filtered(destacadas);
  const otrasShown = onlyDestacadas ? [] : filtered(otras);

  const totalDestacadas = destacadas.length;
  const totalAll = allMarcas.length;

  // ── Acciones ──────────────────────────────────────────────────────────
  const toggleDestacada = (m: MarcaAdmin) => {
    // Al destacar por primera vez, asignarle un orden al final.
    const patch: Partial<MarcaAdmin> = { destacada: !m.destacada };
    if (!m.destacada) {
      patch.orden = (destacadas.at(-1)?.orden ?? 0) + 10;
    }
    updateMut.mutate({ id: m.id, ...patch });
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const oldIndex = destacadasShown.findIndex((m) => m.id === active.id);
    const newIndex = destacadasShown.findIndex((m) => m.id === over.id);
    if (oldIndex < 0 || newIndex < 0) return;

    const next = arrayMove(destacadasShown, oldIndex, newIndex);
    const updates = next.map((m, i) => ({ id: m.id, orden: (i + 1) * 10 }));
    reorderMut.mutate(updates);
  };

  const openLogoUpload = (id: number) => {
    uploadingForId.current = id;
    fileInputRef.current?.click();
  };

  const onFileChosen = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    const id = uploadingForId.current;
    if (file && id != null) {
      uploadLogoMut.mutate({ id, file });
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
    uploadingForId.current = null;
  };

  const startRename = (m: MarcaAdmin) => {
    setRenaming(m);
    setRenameValue(m.nombre);
  };

  const submitRename = () => {
    if (!renaming) return;
    const trimmed = renameValue.trim();
    if (!trimmed || trimmed === renaming.nombre) {
      setRenaming(null);
      return;
    }
    updateMut.mutate(
      { id: renaming.id, nombre: trimmed },
      {
        onSuccess: () => {
          toast.success(`Renombrada a "${trimmed}"`);
          setRenaming(null);
        },
      },
    );
  };

  const goToProducts = (m: MarcaAdmin) => {
    // El listado /admin/equipos filtra por `q` que matchea nombre/marca/modelo/serie.
    navigate({ to: "/admin/equipos", search: { q: m.nombre } as never });
  };

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  return (
    <section className="card p-4 space-y-3">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="font-display text-lg text-ink">Marcas</h2>
          <p className="text-sm text-muted-foreground">
            Tocá la estrella para que aparezcan en el carrusel público. Arrastrá las destacadas para
            cambiar el orden. Usá el menú ⋯ para subir logo, renombrar o eliminar.
          </p>
        </div>
        <div className="text-xs text-muted-foreground tabular-nums">
          <span className="font-medium text-ink">{totalDestacadas}</span> destacadas ·{" "}
          <span className="font-medium text-ink">{totalAll}</span> totales
        </div>
      </header>

      <div className="flex flex-wrap items-center gap-2">
        <Input
          placeholder="Buscar marca…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="h-9 max-w-xs"
        />
        <label className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer select-none">
          {/* eslint-disable-next-line no-restricted-syntax -- checkbox nativo: el DS Checkbox es Radix (otra API) */}
          <input
            type="checkbox"
            checked={onlyDestacadas}
            onChange={(e) => setOnlyDestacadas(e.target.checked)}
            className="h-4 w-4 cursor-pointer"
          />
          Solo destacadas
        </label>
      </div>

      {listQ.isLoading && <ListSkeleton rows={6} className="py-2" />}
      {listQ.error && (
        <ErrorState error={listQ.error} onRetry={() => listQ.refetch()} className="py-6" />
      )}

      {!listQ.isLoading && duplicateGroups.length > 0 && (
        <div className="rounded-md border border-amber/40 bg-amber-soft/50 p-3 space-y-2">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-ink" />
            <span className="text-sm font-medium text-ink">
              Marcas posiblemente duplicadas ({duplicateGroups.length})
            </span>
          </div>
          {duplicateGroups.map((group, gi) => {
            const sorted = [...group].sort((a, b) => b.total - a.total);
            const target = sorted[0];
            const sources = sorted.slice(1);
            return (
              <div key={gi} className="rounded bg-background/60 px-3 py-2 text-xs space-y-1.5">
                <div className="text-muted-foreground">
                  Mantener <span className="font-medium text-ink">{target.nombre}</span> (
                  {target.total} equipos):
                </div>
                {sources.map((src) => (
                  <div key={src.id} className="flex items-center gap-2">
                    <span className="text-ink flex-1 truncate">
                      {src.nombre} <span className="text-muted-foreground">({src.total})</span>
                    </span>
                    <ArrowRight className="h-3 w-3 text-muted-foreground shrink-0" />
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={async () => {
                        if (
                          await confirm({
                            title: `¿Fusionar "${src.nombre}" en "${target.nombre}"?`,
                            description: `Los ${src.total} equipos pasarán a "${target.nombre}" y "${src.nombre}" se borrará.`,
                            danger: true,
                            confirmLabel: "Fusionar",
                          })
                        ) {
                          mergeMut.mutate({ sourceId: src.id, targetId: target.id });
                        }
                      }}
                      disabled={mergeMut.isPending}
                      className="text-2xs font-mono uppercase tracking-wider"
                    >
                      Fusionar
                    </Button>
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      )}

      {!listQ.isLoading && (
        <div className="space-y-4">
          {/* Destacadas con drag-drop */}
          <div className="space-y-1">
            <div className="text-2xs uppercase tracking-wider text-muted-foreground px-1">
              Destacadas — orden del carrusel
            </div>
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragEnd={handleDragEnd}
            >
              <SortableContext
                items={destacadasShown.map((m) => m.id)}
                strategy={verticalListSortingStrategy}
              >
                <div className="border hairline rounded-md divide-y divide-muted/40">
                  {destacadasShown.length > 0 ? (
                    destacadasShown.map((m) => (
                      <SortableMarcaRow
                        key={m.id}
                        marca={m}
                        draggable
                        disabled={updateMut.isPending || reorderMut.isPending}
                        onToggleDestacada={() => toggleDestacada(m)}
                        onUploadLogo={() => openLogoUpload(m.id)}
                        onRename={() => startRename(m)}
                        onViewProducts={() => goToProducts(m)}
                        onDelete={() => setDeleting(m)}
                      />
                    ))
                  ) : (
                    <div className="text-xs text-muted-foreground p-4 text-center">
                      {search ? "Sin resultados en destacadas" : "Aún no destacaste ninguna marca."}
                    </div>
                  )}
                </div>
              </SortableContext>
            </DndContext>
          </div>

          {/* Otras marcas (no destacadas) */}
          {otrasShown.length > 0 && (
            <div className="space-y-1">
              <div className="text-2xs uppercase tracking-wider text-muted-foreground px-1">
                Otras marcas — no aparecen en el carrusel
              </div>
              <div className="border hairline rounded-md divide-y divide-muted/40">
                {otrasShown.map((m) => (
                  <SortableMarcaRow
                    key={m.id}
                    marca={m}
                    draggable={false}
                    disabled={updateMut.isPending}
                    onToggleDestacada={() => toggleDestacada(m)}
                    onUploadLogo={() => openLogoUpload(m.id)}
                    onRename={() => startRename(m)}
                    onViewProducts={() => goToProducts(m)}
                    onDelete={() => setDeleting(m)}
                  />
                ))}
              </div>
            </div>
          )}

          {!onlyDestacadas && otras.length > 0 && otrasShown.length === 0 && search && (
            <div className="text-xs text-muted-foreground text-center py-2">
              Sin resultados en otras marcas
            </div>
          )}

          {allMarcas.length === 0 && (
            <div className="text-xs text-muted-foreground py-4 text-center">
              No hay marcas todavía. Se crean automáticamente cuando agregás equipos.
            </div>
          )}
        </div>
      )}

      {/* eslint-disable-next-line no-restricted-syntax -- input file: no hay componente DS */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={onFileChosen}
      />

      {/* Modal de renombrar */}
      <Dialog open={!!renaming} onOpenChange={(v) => !v && setRenaming(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Renombrar marca</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <Input
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              autoFocus
              onKeyDown={(e) => e.key === "Enter" && submitRename()}
            />
            {renaming && renaming.total > 0 && (
              <p className="text-xs text-muted-foreground">
                Esta marca tiene <strong>{renaming.total} equipos</strong> asociados. Al cambiar el
                nombre, los productos siguen asociados al mismo registro.
              </p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRenaming(null)}>
              Cancelar
            </Button>
            <Button onClick={submitRename} disabled={updateMut.isPending}>
              Guardar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Confirm delete */}
      <AlertDialog open={!!deleting} onOpenChange={(v) => !v && setDeleting(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Eliminar "{deleting?.nombre}"</AlertDialogTitle>
            <AlertDialogDescription>
              {deleting && deleting.total > 0
                ? `Esta marca tiene ${deleting.total} equipos asociados y no se puede eliminar. Fusionala con otra desde el panel de duplicadas, o reasigná los equipos.`
                : "Esta acción no se puede deshacer."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (deleting && deleting.total === 0) {
                  deleteMut.mutate(deleting.id, {
                    onSuccess: () => setDeleting(null),
                  });
                }
              }}
              disabled={!deleting || deleting.total > 0 || deleteMut.isPending}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Eliminar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}

// ── Fila ────────────────────────────────────────────────────────────────

function MarcaAvatar({ marca }: { marca: MarcaAdmin }) {
  if (marca.logo_url) {
    if (isSvgUrl(marca.logo_url)) {
      return (
        <InlineSvg
          url={marca.logo_url}
          ariaLabel={marca.nombre}
          className="h-8 w-8 rounded bg-muted/30 p-1 shrink-0 text-ink"
          fallback={
            <img
              loading="lazy"
              decoding="async"
              src={marca.logo_url}
              alt={marca.nombre}
              className="h-8 w-8 rounded object-contain bg-muted/30 shrink-0"
              onError={(e) => (e.currentTarget.style.display = "none")}
            />
          }
        />
      );
    }
    return (
      <img
        loading="lazy"
        decoding="async"
        src={marca.logo_url}
        alt={marca.nombre}
        className="h-8 w-8 rounded object-contain bg-muted/30 shrink-0"
        onError={(e) => (e.currentTarget.style.display = "none")}
      />
    );
  }
  const initial = marca.nombre.trim().charAt(0).toUpperCase() || "?";
  return (
    <div className="h-8 w-8 rounded grid place-items-center bg-muted text-xs font-medium text-muted-foreground shrink-0">
      {initial}
    </div>
  );
}

type RowProps = {
  marca: MarcaAdmin;
  draggable: boolean;
  disabled: boolean;
  onToggleDestacada: () => void;
  onUploadLogo: () => void;
  onRename: () => void;
  onViewProducts: () => void;
  onDelete: () => void;
};

function SortableMarcaRow(props: RowProps) {
  const { marca, draggable, disabled } = props;
  const sortable = useSortable({ id: marca.id, disabled: !draggable });
  const style = {
    transform: CSS.Transform.toString(sortable.transform),
    transition: sortable.transition,
  };

  return (
    <div
      ref={sortable.setNodeRef}
      style={style}
      className="flex items-center gap-2 px-2 py-2 sm:px-3 sm:gap-3 hover:bg-muted/30 transition"
    >
      {draggable ? (
        <button
          {...sortable.attributes}
          {...sortable.listeners}
          className="cursor-grab active:cursor-grabbing h-5 w-5 grid place-items-center text-muted-foreground hover:text-foreground shrink-0"
          title="Arrastrar para reordenar"
          aria-label={`Reordenar ${marca.nombre}`}
        >
          <GripVertical className="h-4 w-4" />
        </button>
      ) : (
        <div className="h-5 w-5 shrink-0" aria-hidden />
      )}

      <MarcaAvatar marca={marca} />

      <div className="flex-1 min-w-0">
        <div className="truncate text-sm text-ink">{marca.nombre}</div>
        <div className="text-2xs text-muted-foreground tabular-nums">
          {marca.total} {marca.total === 1 ? "equipo" : "equipos"}
        </div>
      </div>

      <button
        onClick={props.onToggleDestacada}
        disabled={disabled}
        className={`h-8 w-8 grid place-items-center rounded-md transition disabled:opacity-50 shrink-0 ${
          marca.destacada
            ? "text-ink hover:bg-amber-soft"
            : "text-muted-foreground/40 hover:text-muted-foreground hover:bg-muted"
        }`}
        title={marca.destacada ? "Quitar de destacadas" : "Destacar en home"}
        aria-label={
          marca.destacada ? `Quitar ${marca.nombre} de destacadas` : `Destacar ${marca.nombre}`
        }
      >
        <Star className={`h-4 w-4 ${marca.destacada ? "fill-current" : ""}`} />
      </button>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            className="h-8 w-8 grid place-items-center rounded-md text-muted-foreground hover:text-foreground hover:bg-muted shrink-0"
            aria-label={`Acciones de ${marca.nombre}`}
          >
            <MoreHorizontal className="h-4 w-4" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-44">
          <DropdownMenuItem onClick={props.onUploadLogo}>
            <Upload className="mr-2 h-4 w-4" />
            Subir logo
          </DropdownMenuItem>
          <DropdownMenuItem onClick={props.onRename}>
            <Pencil className="mr-2 h-4 w-4" />
            Renombrar
          </DropdownMenuItem>
          <DropdownMenuItem onClick={props.onViewProducts}>
            <ExternalLink className="mr-2 h-4 w-4" />
            Ver productos
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onClick={props.onDelete}
            disabled={marca.total > 0}
            className="text-destructive focus:text-destructive"
          >
            <Trash2 className="mr-2 h-4 w-4" />
            Eliminar
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
