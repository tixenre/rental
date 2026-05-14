/**
 * EquiposEnCategoriaList — lista expandible de equipos asignados a una
 * categoría. Se renderea anidada en el árbol de CategoriasSection cuando
 * el usuario abre el disclosure.
 *
 * Backend: usa `/api/equipos?categoria=<nombre>` que matchea recursivamente
 * (incluye descendientes). Para mostrar SOLO los equipos asignados
 * directamente a esta categoría, filtramos client-side por categorias[].
 */

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, X, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { adminApi, type Equipo } from "@/lib/admin/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function EquiposEnCategoriaList({
  categoriaId,
  categoriaNombre,
  count,
}: {
  categoriaId: number;
  categoriaNombre: string;
  count: number;
}) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);

  const equiposQ = useQuery({
    queryKey: ["admin", "equipos-en-categoria", categoriaId],
    queryFn: () =>
      adminApi.listEquipos({
        categoria: categoriaNombre,
        per_page: 500,
      }),
    enabled: open,
    staleTime: 30_000,
  });

  // Filtrar solo equipos DIRECTAMENTE asignados a esta categoría
  // (no descendientes). El backend usa CTE recursivo, así que la lista
  // viene con todos los de la rama.
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

  if (count === 0) return null;

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-ink transition shrink-0"
        title={open ? "Ocultar equipos" : "Ver equipos asignados directamente"}
      >
        <ChevronRight
          className={cn(
            "h-3 w-3 transition-transform",
            open && "rotate-90",
          )}
        />
        <span className="tabular-nums">{count}</span>
      </button>

      {open && (
        <div className="basis-full ml-10 mt-1 border-l hairline pl-2">
          {equiposQ.isLoading && (
            <div className="flex items-center gap-2 py-2 text-[11px] text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" /> Cargando…
            </div>
          )}
          {equiposQ.isSuccess && equiposDirectos.length === 0 && (
            <div className="py-2 text-[11px] text-muted-foreground italic">
              No hay equipos asignados directamente acá. Los {count} que cuenta
              esta categoría son de sus subcategorías.
            </div>
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
      )}
    </>
  );
}

function EquipoRow({
  equipo, onRemove, disabled,
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
            onError={(e) => ((e.currentTarget.style.opacity = "0"))}
            loading="lazy"
          />
        ) : null}
      </div>
      <div className="flex-1 min-w-0">
        <div className="truncate text-ink">{equipo.nombre}</div>
        {equipo.marca && (
          <div className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground truncate">
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
