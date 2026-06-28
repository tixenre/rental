/**
 * Equipos dentro de una categoría — toggle + panel separados.
 *
 * Antes era un solo componente que renderizaba todo inline, lo que rompía
 * la row al expandirse. Ahora:
 *  - `EquiposCountToggle` se renderea EN la row (botón "▶ N" o "+ equipos").
 *  - `EquiposPanel` se renderea BAJO la row con indent, mimicando cómo se
 *    ven las subcategorías al expandir su padre.
 *
 * El estado `open` lo posee el parent row para poder decidir DÓNDE
 * renderizar el panel (fuera del flex container de la row).
 */

import { useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { X, ChevronRight, Plus, PackageOpen } from "lucide-react";
import { toast } from "sonner";
import { adminApi, type Equipo } from "@/lib/admin/api";
import { Button } from "@/design-system/ui/button";
import { ListSkeleton } from "@/components/admin/skeletons";
import { ErrorState } from "@/components/admin/ErrorState";
import { EmptyState } from "@/components/rental/EmptyState";
import { cn } from "@/lib/utils";

// ── Toggle ─────────────────────────────────────────────────────────────

export function EquiposCountToggle({
  count,
  isOpen,
  onToggle,
  onAddWhenEmpty,
}: {
  count: number;
  isOpen: boolean;
  onToggle: () => void;
  /** Si la categoría no tiene equipos, mostrar un CTA "+ equipos"
   *  en lugar del count. */
  onAddWhenEmpty?: () => void;
}) {
  if (count === 0) {
    if (!onAddWhenEmpty) return null;
    return (
      <button
        type="button"
        onClick={onAddWhenEmpty}
        className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-ink transition shrink-0 underline-offset-2 hover:underline"
        title="Agregar equipos a esta categoría"
      >
        <Plus className="h-3 w-3" /> equipos
      </button>
    );
  }
  return (
    <button
      type="button"
      onClick={onToggle}
      className="flex items-center gap-1 text-xs text-muted-foreground hover:text-ink transition shrink-0"
      title={isOpen ? "Ocultar equipos" : "Ver equipos asignados directamente"}
    >
      <ChevronRight className={cn("h-3 w-3 transition-transform", isOpen && "rotate-90")} />
      <span className="tabular-nums">{count}</span>
    </button>
  );
}

// ── Panel ──────────────────────────────────────────────────────────────

export function EquiposPanel({
  categoriaId,
  categoriaNombre,
  indentLevel = 1,
  onAddEquipos,
}: {
  categoriaId: number;
  categoriaNombre: string;
  /** 1 = hijo de root (indent ml-10), 2 = nieto (ml-16). */
  indentLevel?: 1 | 2 | 3;
  onAddEquipos?: (id: number, nombre: string) => void;
}) {
  const qc = useQueryClient();

  const equiposQ = useQuery({
    queryKey: ["admin", "equipos-en-categoria", categoriaId],
    queryFn: () => adminApi.listEquipos({ categoria: categoriaNombre, per_page: 500 }),
    staleTime: 30_000,
  });

  // El backend usa CTE recursivo: trae equipos de la categoría Y de
  // sus descendientes. Filtramos client-side por categorias[].id para
  // mostrar SOLO los asignados directamente.
  const equiposDirectos = useMemo(() => {
    if (!equiposQ.data) return [];
    return equiposQ.data.items.filter((e) =>
      (e.categorias ?? []).some((c) => c.id === categoriaId),
    );
  }, [equiposQ.data, categoriaId]);

  const removeMut = useMutation({
    mutationFn: (equipoId: number) =>
      adminApi.bulkAction({
        ids: [equipoId],
        action: "remove_categoria",
        categoria_id: categoriaId,
      }),
    onSuccess: () => {
      toast.success("Equipo quitado de la categoría");
      qc.invalidateQueries({ queryKey: ["admin", "equipos-en-categoria", categoriaId] });
      qc.invalidateQueries({ queryKey: ["admin", "categorias"] });
      qc.invalidateQueries({ queryKey: ["admin", "equipos"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const indentClass = indentLevel === 1 ? "ml-10" : indentLevel === 2 ? "ml-16" : "ml-20";

  return (
    <div className={cn(indentClass, "border-l hairline pl-3 py-1 space-y-1")}>
      {onAddEquipos && (
        <button
          type="button"
          onClick={() => onAddEquipos(categoriaId, categoriaNombre)}
          className="inline-flex items-center gap-1 text-xs text-ink hover:text-ink transition py-0.5"
          title="Agregar más equipos a esta categoría"
        >
          <Plus className="h-3 w-3" /> Agregar equipos
        </button>
      )}
      {equiposQ.isLoading && <ListSkeleton rows={3} className="py-1" />}
      {equiposQ.isError && (
        <ErrorState error={equiposQ.error} onRetry={() => equiposQ.refetch()} className="py-4" />
      )}
      {equiposQ.isSuccess && equiposDirectos.length === 0 && (
        <EmptyState
          icon={<PackageOpen className="h-6 w-6" />}
          title="Sin equipos directos"
          sub="Los que cuenta esta categoría vienen de sus subcategorías."
          className="py-4"
        />
      )}
      {equiposDirectos.length > 0 && (
        <ul className="space-y-0.5">
          {equiposDirectos.map((eq) => (
            <EquipoRow
              key={eq.id}
              equipo={eq}
              onRemove={() => removeMut.mutate(eq.id)}
              disabled={removeMut.isPending}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

function EquipoRow({
  equipo,
  onRemove,
  disabled,
}: {
  equipo: Equipo;
  onRemove: () => void;
  disabled: boolean;
}) {
  return (
    <li className="flex items-center gap-2 py-1 text-xs">
      <div className="relative aspect-square w-7 shrink-0 overflow-hidden rounded bg-muted/40">
        {equipo.foto_url ? (
          <img
            src={equipo.foto_url}
            alt={equipo.nombre}
            className="h-full w-full object-contain p-0.5"
            onError={(e) => (e.currentTarget.style.opacity = "0")}
            loading="lazy"
          />
        ) : null}
      </div>
      <div className="flex-1 min-w-0">
        <div className="truncate text-ink">{equipo.nombre}</div>
        {equipo.marca && (
          <div className="font-mono text-2xs uppercase tracking-wider text-muted-foreground truncate">
            {equipo.marca}
          </div>
        )}
      </div>
      <Button
        size="icon"
        variant="ghost"
        className="h-6 w-6 text-muted-foreground hover:text-destructive"
        onClick={onRemove}
        disabled={disabled}
        title="Quitar de esta categoría"
      >
        <X className="h-3 w-3" />
      </Button>
    </li>
  );
}
