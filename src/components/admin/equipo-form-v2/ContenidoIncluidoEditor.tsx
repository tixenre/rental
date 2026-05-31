/**
 * Editor de "contenido incluido" (dim. 3 del modelo de productos, B1 #635).
 * Permite agregar/editar/eliminar ítems {nombre, cantidad, foto_url?} de la caja.
 * Fotos: reusa el endpoint de upload de equipo (POST upload-foto / upload-foto-from-url).
 */

import { useRef, useState } from "react";
import { Plus, Trash2, Upload, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { uploadFileToBucket } from "@/lib/equipment/photos";
import type { ContenidoIncluidoItem } from "@/data/equipment";

export function ContenidoIncluidoEditor({
  equipoId,
  items,
  onChange,
}: {
  equipoId: number;
  items: ContenidoIncluidoItem[];
  onChange: (next: ContenidoIncluidoItem[]) => void;
}) {
  const [uploadingIdx, setUploadingIdx] = useState<number | null>(null);

  const update = (idx: number, patch: Partial<ContenidoIncluidoItem>) => {
    const next = items.map((it, i) => (i === idx ? { ...it, ...patch } : it));
    onChange(next);
  };

  const remove = (idx: number) => {
    onChange(items.filter((_, i) => i !== idx));
  };

  const add = () => {
    onChange([...items, { nombre: "", cantidad: 1, foto_url: null }]);
  };

  const handleFotoUpload = async (idx: number, file: File) => {
    setUploadingIdx(idx);
    try {
      const url = await uploadFileToBucket(equipoId, file);
      update(idx, { foto_url: url });
      toast.success("Foto subida");
    } catch (e) {
      toast.error(`No se pudo subir: ${e instanceof Error ? e.message : ""}`);
    } finally {
      setUploadingIdx(null);
    }
  };

  return (
    <div className="space-y-3">
      <Label className="text-xs uppercase tracking-wide text-muted-foreground">
        Ítems ({items.length})
      </Label>

      {items.length === 0 ? (
        <p className="text-xs text-muted-foreground italic">
          Sin ítems. Usá el botón de abajo para agregar.
        </p>
      ) : (
        <div className="space-y-2">
          {items.map((it, idx) => (
            <ContenidoItemRow
              key={idx}
              item={it}
              uploading={uploadingIdx === idx}
              onChangeName={(v) => update(idx, { nombre: v })}
              onChangeCantidad={(v) => update(idx, { cantidad: v })}
              onUploadFoto={(f) => handleFotoUpload(idx, f)}
              onRemove={() => remove(idx)}
            />
          ))}
        </div>
      )}

      <Button type="button" size="sm" variant="outline" onClick={add}>
        <Plus className="h-3.5 w-3.5 mr-1" /> Agregar ítem
      </Button>
    </div>
  );
}

function ContenidoItemRow({
  item,
  uploading,
  onChangeName,
  onChangeCantidad,
  onUploadFoto,
  onRemove,
}: {
  item: ContenidoIncluidoItem;
  uploading: boolean;
  onChangeName: (v: string) => void;
  onChangeCantidad: (v: number) => void;
  onUploadFoto: (f: File) => void;
  onRemove: () => void;
}) {
  const fileRef = useRef<HTMLInputElement | null>(null);

  return (
    <div className="flex items-center gap-2 rounded-md border hairline px-2 py-1.5 bg-background">
      {/* Miniatura de foto */}
      <button
        type="button"
        title="Subir foto"
        onClick={() => fileRef.current?.click()}
        disabled={uploading}
        className="relative h-10 w-10 shrink-0 rounded bg-muted/30 overflow-hidden hover:opacity-80 transition"
      >
        {uploading ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
          </div>
        ) : item.foto_url ? (
          <img
            src={item.foto_url}
            alt=""
            className="h-full w-full object-contain"
            onError={(e) => {
              (e.target as HTMLImageElement).style.opacity = "0";
            }}
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center">
            <Upload className="h-3.5 w-3.5 text-muted-foreground/60" />
          </div>
        )}
      </button>
      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onUploadFoto(f);
          e.target.value = "";
        }}
      />

      {/* Nombre */}
      <Input
        value={item.nombre}
        onChange={(e) => onChangeName(e.target.value)}
        placeholder="Ej: Cargador, Cable HDMI, Estuche…"
        className="flex-1 h-8 text-sm"
      />

      {/* Cantidad */}
      <Input
        type="number"
        min={1}
        value={item.cantidad}
        onChange={(e) => onChangeCantidad(Math.max(1, parseInt(e.target.value || "1", 10)))}
        className="w-16 h-8 text-center text-sm"
        aria-label="Cantidad"
      />

      <Button
        type="button"
        size="icon"
        variant="ghost"
        className="h-8 w-8"
        onClick={onRemove}
        title="Eliminar ítem"
      >
        <Trash2 className="h-4 w-4" />
      </Button>
    </div>
  );
}
