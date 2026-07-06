import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Eye, EyeOff, Film, GripVertical, Image, Pencil, Trash2 } from "lucide-react";

import { IconButton } from "@/design-system/ui/icon-button";
import { Pill } from "@/design-system/ui/Pill";
import { cn } from "@/lib/utils";
import type { EstudioTrabajo } from "@/lib/admin/api";

export function SortableTrabajoCard({
  trabajo,
  onEdit,
  onDelete,
  onToggleActivo,
}: {
  trabajo: EstudioTrabajo;
  onEdit: (t: EstudioTrabajo) => void;
  onDelete: (id: number) => void;
  onToggleActivo: (id: number, activo: boolean) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: trabajo.id,
  });
  const style = { transform: CSS.Transform.toString(transform), transition };

  // Thumbnail = primer medio del carrusel (link procesado o foto).
  const first = trabajo.media?.[0];
  const thumb = first
    ? first.kind === "foto"
      ? (first.url_sm ?? first.url ?? null)
      : (first.thumbnail ?? null)
    : null;

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        "flex items-center gap-3 rounded-xl border hairline bg-background p-3 transition-shadow",
        isDragging ? "shadow-lg opacity-80" : "",
      )}
    >
      {/* Drag handle */}
      <button
        {...attributes}
        {...listeners}
        className="cursor-grab text-muted-foreground hover:text-ink p-1 touch-none"
        aria-label="Arrastrar"
      >
        <GripVertical className="h-4 w-4" />
      </button>

      {/* Thumbnail */}
      <div className="h-12 w-16 rounded-lg overflow-hidden border hairline bg-muted/30 shrink-0">
        {thumb ? (
          <img src={thumb} alt="" className="h-full w-full object-cover" />
        ) : (
          <div className="h-full w-full flex items-center justify-center">
            {trabajo.tipo === "video" ? (
              <Film className="h-5 w-5 text-muted-foreground/40" />
            ) : (
              <Image className="h-5 w-5 text-muted-foreground/40" />
            )}
          </div>
        )}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-ink truncate">
          {trabajo.titulo || <span className="text-muted-foreground italic">Sin título</span>}
        </p>
        <p className="text-xs text-muted-foreground truncate">{trabajo.realizador || "—"}</p>
      </div>

      {/* Cantidad de medios */}
      <Pill tone="neutral" className="font-mono uppercase tracking-[0.1em]">
        {trabajo.media.length} {trabajo.media.length === 1 ? "medio" : "medios"}
      </Pill>

      {/* Actions */}
      <div className="flex items-center gap-1 shrink-0">
        <IconButton
          aria-label={trabajo.activo ? "Ocultar" : "Publicar"}
          size="xs"
          onClick={() => onToggleActivo(trabajo.id, !trabajo.activo)}
          className="rounded-lg hover:bg-muted"
        >
          {trabajo.activo ? (
            <Eye className="h-3.5 w-3.5 text-muted-foreground" />
          ) : (
            <EyeOff className="h-3.5 w-3.5 text-muted-foreground/40" />
          )}
        </IconButton>
        <IconButton
          aria-label="Editar"
          size="xs"
          onClick={() => onEdit(trabajo)}
          className="rounded-lg hover:bg-muted"
        >
          <Pencil className="h-3.5 w-3.5 text-muted-foreground" />
        </IconButton>
        <IconButton
          aria-label="Eliminar"
          size="xs"
          onClick={() => onDelete(trabajo.id)}
          className="rounded-lg hover:bg-muted text-destructive/70 hover:text-destructive hover:bg-destructive/10"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </IconButton>
      </div>
    </div>
  );
}
