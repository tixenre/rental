/**
 * Editor de "contenido incluido" (dim. 3 del modelo de productos, B1 #635).
 * Permite agregar/editar/eliminar ítems {nombre, cantidad, foto_url?} de la caja.
 * Fotos: reusa el endpoint de upload de equipo (POST upload-foto / upload-foto-from-url).
 */

import { useRef, useState } from "react";
import { Plus, Trash2, Upload } from "lucide-react";
import { Spinner } from "@/design-system/ui/spinner";
import { toast } from "sonner";

import { Input } from "@/design-system/ui/input";
import { DraftNumberInput } from "@/design-system/ui/draft-number-input";
import { Button } from "@/design-system/ui/button";
import { Label } from "@/design-system/ui/label";
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
  const [uploadingItem, setUploadingItem] = useState<ContenidoIncluidoItem | null>(null);

  // `items` siempre al día para leer dentro de callbacks async (la subida de
  // foto tarda; si en el medio el admin agrega/borra un ítem, el closure de
  // `handleFotoUpload` que arrancó antes seguía viendo el array de cuando
  // arrancó — el índice capturado en el click podía terminar apuntando a un
  // ítem distinto, o a uno inexistente).
  const itemsRef = useRef(items);
  itemsRef.current = items;

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

  const handleFotoUpload = async (item: ContenidoIncluidoItem, file: File) => {
    setUploadingItem(item);
    try {
      const url = await uploadFileToBucket(equipoId, file);
      // Ubicar el ítem por REFERENCIA (no por índice capturado al click):
      // `update`/`remove` solo reemplazan el ítem editado — los demás
      // conservan su referencia entre renders — así que sigue siendo el
      // mismo objeto aunque el array se haya reordenado/mutado mientras
      // la subida estaba en curso.
      const current = itemsRef.current;
      const idx = current.indexOf(item);
      if (idx === -1) {
        toast.error("El ítem se eliminó antes de terminar la subida — foto no aplicada");
        return;
      }
      onChange(current.map((it, i) => (i === idx ? { ...it, foto_url: url } : it)));
      toast.success("Foto subida");
    } catch (e) {
      toast.error(`No se pudo subir: ${e instanceof Error ? e.message : ""}`);
    } finally {
      setUploadingItem(null);
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
              uploading={uploadingItem === it}
              onChangeName={(v) => update(idx, { nombre: v })}
              onChangeCantidad={(v) => update(idx, { cantidad: v })}
              onUploadFoto={(f) => handleFotoUpload(it, f)}
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
        className="relative h-11 w-11 shrink-0 rounded bg-muted/30 overflow-hidden hover:opacity-80 transition"
      >
        {uploading ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <Spinner size="sm" className="text-muted-foreground" />
          </div>
        ) : item.foto_url ? (
          <img
            loading="lazy"
            decoding="async"
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
      {/* eslint-disable-next-line no-restricted-syntax -- input file: no hay componente DS */}
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
      <DraftNumberInput
        min={1}
        value={item.cantidad}
        onCommit={onChangeCantidad}
        className="w-16 h-8 text-center text-sm"
        ariaLabel="Cantidad"
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
