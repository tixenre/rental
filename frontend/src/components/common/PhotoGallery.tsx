/**
 * PhotoGallery — galería de fotos genérica/reusable para el back-office.
 *
 * Pensada para ser adoptada por otras entidades (equipos, etc.) sin cambios.
 * La lógica de upload/delete/reorder vive en el padre; este componente solo
 * renderiza y emite callbacks.
 */

import { useRef } from "react";
import { ImageIcon, Trash2, Star, ChevronUp, ChevronDown, Upload } from "lucide-react";
import { Spinner } from "@/design-system/ui/spinner";
import { cn } from "@/lib/utils";

export type GalleryFoto = {
  id: number;
  url: string;
  orden: number;
  es_principal: boolean;
};

type Props = {
  fotos: GalleryFoto[];
  onUpload: (files: FileList) => void;
  onDelete: (id: number) => void;
  onReorder: (fotos: GalleryFoto[]) => void;
  onSetPrincipal: (id: number) => void;
  uploading?: boolean;
  disabled?: boolean;
};

export function PhotoGallery({
  fotos,
  onUpload,
  onDelete,
  onReorder,
  onSetPrincipal,
  uploading = false,
  disabled = false,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);

  function movePhoto(index: number, dir: -1 | 1) {
    const next = [...fotos];
    const swapIdx = index + dir;
    if (swapIdx < 0 || swapIdx >= next.length) return;
    [next[index], next[swapIdx]] = [next[swapIdx], next[index]];
    const reindexed = next.map((f, i) => ({ ...f, orden: i }));
    onReorder(reindexed);
  }

  return (
    <div className="space-y-4">
      {/* Upload trigger */}
      <div>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept="image/*"
          className="hidden"
          onChange={(e) => {
            if (e.target.files?.length) {
              onUpload(e.target.files);
              e.target.value = "";
            }
          }}
          disabled={disabled || uploading}
        />
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={disabled || uploading}
          className={cn(
            "flex w-full items-center justify-center gap-2 rounded-xl border-2 border-dashed px-4 py-6 text-sm transition",
            "border-border text-muted-foreground hover:border-ink hover:text-ink",
            "disabled:cursor-not-allowed disabled:opacity-50",
          )}
        >
          {uploading ? (
            <>
              <Spinner size="sm" />
              Subiendo…
            </>
          ) : (
            <>
              <Upload className="h-4 w-4" />
              Subir fotos (podés elegir varias)
            </>
          )}
        </button>
      </div>

      {/* Grid de thumbnails */}
      {fotos.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {fotos.map((foto, idx) => (
            <div
              key={foto.id}
              className={cn(
                "group relative overflow-hidden rounded-xl border bg-surface",
                foto.es_principal ? "border-amber ring-1 ring-amber" : "hairline",
              )}
            >
              <div className="aspect-square w-full overflow-hidden">
                <img src={foto.url} alt="" className="h-full w-full object-cover" loading="lazy" />
              </div>

              {/* Badge principal */}
              {foto.es_principal && (
                <div className="absolute left-2 top-2 flex items-center gap-1 rounded-full bg-amber px-2 py-0.5 text-2xs font-semibold uppercase tracking-wide text-ink">
                  <Star className="h-2.5 w-2.5 fill-current" />
                  Principal
                </div>
              )}

              {/* Controles superpuestos. En táctil (sin hover) van SIEMPRE
                  visibles — si no, en mobile no hay forma de borrar/reordenar.
                  En desktop (hover disponible) se revelan al pasar el mouse. */}
              <div className="absolute inset-0 flex flex-col justify-between p-1.5 opacity-100 transition-opacity [@media(hover:hover)]:opacity-0 [@media(hover:hover)]:group-hover:opacity-100">
                {/* Arriba: borrar */}
                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={() => onDelete(foto.id)}
                    disabled={disabled || uploading}
                    title="Eliminar"
                    className="flex h-7 w-7 items-center justify-center rounded-lg bg-background/90 text-destructive shadow hover:bg-destructive hover:text-white disabled:opacity-50"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>

                {/* Abajo: reordenar + marcar principal */}
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => movePhoto(idx, -1)}
                    disabled={disabled || uploading || idx === 0}
                    title="Mover arriba"
                    className="flex h-7 w-7 items-center justify-center rounded-lg bg-background/90 shadow hover:bg-background disabled:opacity-30"
                  >
                    <ChevronUp className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => movePhoto(idx, 1)}
                    disabled={disabled || uploading || idx === fotos.length - 1}
                    title="Mover abajo"
                    className="flex h-7 w-7 items-center justify-center rounded-lg bg-background/90 shadow hover:bg-background disabled:opacity-30"
                  >
                    <ChevronDown className="h-3.5 w-3.5" />
                  </button>
                  {!foto.es_principal && (
                    <button
                      type="button"
                      onClick={() => onSetPrincipal(foto.id)}
                      disabled={disabled || uploading}
                      title="Marcar como principal"
                      className="ml-auto flex h-7 w-7 items-center justify-center rounded-lg bg-background/90 shadow hover:bg-amber hover:text-ink disabled:opacity-50"
                    >
                      <Star className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {fotos.length === 0 && !uploading && (
        <div className="flex flex-col items-center gap-2 card py-8 text-muted-foreground">
          <ImageIcon className="h-8 w-8 opacity-30" />
          <p className="text-sm">Sin fotos todavía</p>
        </div>
      )}
    </div>
  );
}
